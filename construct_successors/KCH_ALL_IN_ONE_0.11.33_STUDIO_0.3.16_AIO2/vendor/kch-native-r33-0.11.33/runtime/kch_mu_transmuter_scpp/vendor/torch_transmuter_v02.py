from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import math, torch
from torch import Tensor, nn

@dataclass(frozen=True)
class TransmuterConfig:
    dim:int; num_heads:int=4; lambda_q:float=.3; tau_q:float=.75; q_temperature:float=1.
    laplacian_orientation:Literal["canonical","diffusive"]="canonical"; n_maps:int=3; rho_max:float=.85
    theta_min:float=math.pi/8; theta_gap:float=math.pi/12; fnl_closure_strength:float=.2
    attention_residual:float=.2; fnl_residual:float=.2; toponorm_shrinkage:float=.05; toponorm_eps:float=1e-6; seed:int=101
    def __post_init__(self):
        if self.dim<2 or self.dim%self.num_heads or self.n_maps<2 or not 0<self.rho_max<1 or self.tau_q<=0 or self.q_temperature<=0: raise ValueError("invalid configuration")

class TorchCanonicalTransmuter(nn.Module):
    def __init__(self,c:TransmuterConfig,dtype=torch.float64):
        super().__init__(); self.config=c; d=c.dim; g=torch.Generator().manual_seed(c.seed)
        def xv(a,b):
            z=math.sqrt(6/(a+b)); return nn.Parameter(torch.empty(a,b,dtype=dtype).uniform_(-z,z,generator=g))
        self.w_q,self.w_k,self.w_v,self.w_o=xv(d,d),xv(d,d),xv(d,d),xv(d,d)
        self.w_q4,self.b_q4=xv(d,4),nn.Parameter(torch.zeros(4,dtype=dtype))
        self.raw_rho=nn.Parameter(torch.empty(c.n_maps,dtype=dtype).uniform_(-1,1,generator=g))
        self.raw_theta=nn.Parameter(torch.empty(c.n_maps,dtype=dtype).uniform_(-1,1,generator=g))
        self.fnl_translation=nn.Parameter(torch.empty(c.n_maps,d,dtype=dtype).normal_(0,.05,generator=g))
        self.register_buffer("axes",torch.tensor([[1.,1.],[-1.,1.],[1.,-1.],[-1.,-1.]],dtype=dtype))
        self.register_buffer("low",torch.arange(c.n_maps)%2==0)
    @property
    def fnl_rho(self): return self.config.rho_max*torch.sigmoid(self.raw_rho)
    @property
    def fnl_theta(self):
        c,s=self.config,torch.sigmoid(self.raw_theta)
        return torch.where(self.low,c.theta_min+(math.pi/2-c.theta_gap-c.theta_min)*s,math.pi/2+c.theta_gap+(math.pi-c.theta_min-(math.pi/2+c.theta_gap))*s)
    def _logit(self,x): return torch.log(x)-torch.log1p(-x)
    def load_numpy_reference(self,r):
        with torch.no_grad():
            for k in ("w_q","w_k","w_v","w_o","w_q4","b_q4","fnl_translation"): getattr(self,k).copy_(torch.as_tensor(getattr(r,k),dtype=getattr(self,k).dtype))
            rho=torch.as_tensor(r.fnl_rho,dtype=self.raw_rho.dtype); self.raw_rho.copy_(self._logit((rho/self.config.rho_max).clamp(1e-12,1-1e-12)))
            th=torch.as_tensor(r.fnl_theta,dtype=self.raw_theta.dtype); c=self.config
            lo=torch.where(self.low,torch.full_like(th,c.theta_min),torch.full_like(th,math.pi/2+c.theta_gap)); hi=torch.where(self.low,torch.full_like(th,math.pi/2-c.theta_gap),torch.full_like(th,math.pi-c.theta_min))
            self.raw_theta.copy_(self._logit(((th-lo)/(hi-lo)).clamp(1e-12,1-1e-12)))
        return self
    def _mask(self,x,m):
        if x.ndim!=3 or x.shape[-1]!=self.config.dim or x.shape[1]<2 or not torch.isfinite(x).all(): raise ValueError("invalid x")
        m=torch.ones(x.shape[:2],device=x.device,dtype=torch.bool) if m is None else m
        if m.shape!=x.shape[:2] or m.dtype!=torch.bool or not m.any(1).all(): raise ValueError("invalid mask")
        return m
    def q4_posterior(self,x): return torch.softmax((x@self.w_q4+self.b_q4)/self.config.q_temperature,-1)
    def conformational_laplacian(self,p,m):
        n=p.shape[1]; h=.5*(p.clamp(0,1).sqrt()[:,:,None]-p.clamp(0,1).sqrt()[:,None,:]).square().sum(-1)
        a=p@self.axes.to(p); td=.5*((a[:,:,None]-a[:,None,:]).abs()/2).mean(-1); adj=torch.exp(-(h+td)/self.config.tau_q)
        eye=torch.eye(n,dtype=p.dtype,device=p.device)[None]; adj=adj*(1-eye)*(m[:,:,None]&m[:,None,:]).to(p)
        inv=adj.sum(-1).clamp_min(1e-12).rsqrt(); L=eye-inv[:,:,None]*adj*inv[:,None,:]
        return -.5*(L+L.transpose(-1,-2)) if self.config.laplacian_orientation=="diffusive" else .5*(L+L.transpose(-1,-2))
    def attn(self,x,m,causal):
        b,n,d=x.shape; h=self.config.num_heads; dh=d//h
        q=(x@self.w_q).reshape(b,n,h,dh).transpose(1,2); k=(x@self.w_k).reshape(b,n,h,dh).transpose(1,2); v=(x@self.w_v).reshape(b,n,h,dh).transpose(1,2)
        p=self.q4_posterior(x); L=self.conformational_laplacian(p,m)
        if causal:
            rows=[]
            for t in range(n):
                prefix=self.conformational_laplacian(p[:,:t+1],m[:,:t+1])[:,t,:]
                rows.append(torch.nn.functional.pad(prefix,(0,n-t-1)))
            L=torch.stack(rows,1)
        s=q@k.transpose(-1,-2)/math.sqrt(dh)+self.config.lambda_q*L[:,None]
        ok=m[:,None,None,:]
        if causal: ok=ok&torch.tril(torch.ones(n,n,dtype=torch.bool,device=x.device))[None,None]
        s=torch.where(ok,s,torch.finfo(x.dtype).min); s=torch.where(m[:,None,:,None],s,torch.zeros_like(s))
        y=(torch.softmax(s,-1)@v).transpose(1,2).reshape(b,n,d)@self.w_o
        return y*m[...,None],p,L
    def fnl(self,x):
        d=self.config.dim; ys=[]
        for i in range(self.config.n_maps):
            a,b=(2*i)%d,(2*i+1)%d; e=torch.eye(d,dtype=x.dtype,device=x.device); ea=e[a]; eb=e[b]; t=self.fnl_theta[i]
            R=e+(torch.cos(t)-1)*(torch.outer(ea,ea)+torch.outer(eb,eb))+torch.sin(t)*(torch.outer(eb,ea)-torch.outer(ea,eb))
            ys.append(self.fnl_rho[i]*(x@R.T)+self.fnl_translation[i])
        st=torch.stack(ys); cen=st.mean(0); disp=(st.sub(cen).square().mean(0)+1e-12).sqrt()
        return cen+self.config.fnl_closure_strength*torch.tanh(x-cen)*(1+disp/(1+disp)),disp.mean()
    def topo(self,x,m,causal=False):
        b,n,d=x.shape; w=m.to(x)
        if causal:
            cnt=w.cumsum(1).clamp_min(1); mu=(x*w[...,None]).cumsum(1)/cnt[...,None]; sec=(x[:,:,:,None]*x[:,:,None,:]*w[...,None,None]).cumsum(1); cov=sec/cnt[...,None,None]-mu[:,:,:,None]*mu[:,:,None,:]; cov=cov*(cnt/(cnt-1).clamp_min(1))[...,None,None]
        else:
            cnt=w.sum(1).clamp_min(1); mu=(x*w[...,None]).sum(1,keepdim=True)/cnt[:,None,None]; z=(x-mu)*w[...,None]; cov=z.transpose(-1,-2)@z/(cnt-1).clamp_min(1)[:,None,None]
        eye=torch.eye(d,dtype=x.dtype,device=x.device); tr=cov.diagonal(0,-2,-1).sum(-1)/d; cr=(1-self.config.toponorm_shrinkage)*cov+self.config.toponorm_shrinkage*tr[...,None,None]*eye+self.config.toponorm_eps*eye
        ev=torch.linalg.eigvalsh(cr).clamp_min(self.config.toponorm_eps); lv=.5*ev.log().mean(-1); y=(mu+(x-mu)/(lv.exp()[...,None] if causal else lv.exp()[:,None,None]))*w[...,None]
        return y,lv
    def forward(self,x,attention_mask=None,*,causal=False):
        m=self._mask(x,attention_mask); x=x*m[...,None]; a,p,L=self.attn(x,m,causal); s1,lv1=self.topo(x+self.config.attention_residual*a,m,causal); f,disp=self.fnl(s1); y,lv2=self.topo(s1+self.config.fnl_residual*f*m[...,None],m,causal)
        return y,{"q_probabilities":p,"laplacian":L,"fnl_rho":self.fnl_rho,"fnl_theta":self.fnl_theta,"fnl_dispersion_mean":disp,"toponorm_1_log_volume":lv1,"toponorm_2_log_volume":lv2}
