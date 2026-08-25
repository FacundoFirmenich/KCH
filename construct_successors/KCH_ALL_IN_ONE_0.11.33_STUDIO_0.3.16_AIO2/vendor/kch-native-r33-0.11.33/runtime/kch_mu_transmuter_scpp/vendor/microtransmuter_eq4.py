"""muT-EQ4 standalone electrochemical perceptron; never a Transmuter micro-version."""
from dataclasses import dataclass
import torch
from torch import nn
@dataclass(frozen=True)
class MicroConfig:
 dim:int=8; chemical_dim:int=8; global_dim:int=4; q_types:int=4; seed:int=101
 def __post_init__(self):
  if min(self.dim,self.chemical_dim,self.global_dim)<1 or self.q_types!=4: raise ValueError("invalid config")
class MicroTransmuterEQ4(nn.Module):
 def __init__(self,c=MicroConfig(),dtype=torch.float64):
  super().__init__(); self.c=c; g=torch.Generator().manual_seed(c.seed);d,k,h=c.dim,c.chemical_dim,c.global_dim
  def L(a,b):
   x=nn.Linear(a,b,dtype=dtype);nn.init.xavier_uniform_(x.weight,generator=g);nn.init.zeros_(x.bias);return x
  self.release=L(2*d+k+h,k);self.kinetics=L(2*k+h,k);self.raw_reuptake=nn.Parameter(torch.zeros(k,dtype=dtype));self.q_logits=L(2*d+k+h,4);self.conductance=L(2*d+k+h,4*d);self.q_close=L(4*d,d);self.node=L(2*d+h,d);self.global_update=L(d+h,h)
 def forward(self,e,z=None,h=None,drive=None):
  if e.ndim!=3 or e.shape[-1]!=self.c.dim or not torch.isfinite(e).all():raise ValueError("e must be finite B,N,D")
  b,n,d=e.shape;k,g=self.c.chemical_dim,self.c.global_dim
  if z is None:z=torch.zeros(b,n,n,k,dtype=e.dtype,device=e.device)
  if drive is None:drive=torch.zeros_like(e)
  if drive.shape!=e.shape:raise ValueError("drive shape mismatch")
  if h is None:h=torch.zeros(b,g,dtype=e.dtype,device=e.device)
  if z.shape!=(b,n,n,k) or h.shape!=(b,g):raise ValueError("state shape mismatch")
  pre=e[:,:,None,:].expand(-1,-1,n,-1);post=e[:,None,:,:].expand(-1,n,-1,-1);hh=h[:,None,None,:].expand(-1,n,n,-1);c=torch.sigmoid(z)
  rel=torch.sigmoid(self.release(torch.cat((pre,post,c,hh),-1)));eta=torch.sigmoid(self.raw_reuptake)[None,None,None,:];znext=(1-eta)*z+torch.tanh(self.kinetics(torch.cat((c,rel,hh),-1)));cnext=torch.sigmoid(znext);feat=torch.cat((pre,post,cnext,hh),-1);pi=torch.softmax(self.q_logits(feat),-1);curr=self.conductance(feat).reshape(b,n,n,4,d);typed=(pi[...,None]*curr).reshape(b,n,n,4*d);eye=torch.eye(n,dtype=torch.bool,device=e.device)[None,:,:,None];typed=typed.masked_fill(eye,0);cnext=cnext.masked_fill(eye,0);pi=pi.masked_fill(eye,0);msg=self.q_close(typed).sum(1);hnext=torch.tanh(self.global_update(torch.cat((e.mean(1),h),-1)));enext=torch.tanh(self.node(torch.cat((e,msg,hnext[:,None,:].expand(-1,n,-1)),-1))+drive);return enext,znext,hnext,{"chemical":cnext,"q_probabilities":pi,"typed_currents":typed}
