from sca_dep.model import EvidenceEvent,ProvenanceConstraint,Relation
from .model import Action,World

def routing_scenario():
    events=[EvidenceEvent(f'e{i}',f's{i}',1) for i in range(8)]
    c=[]
    for i in range(6):
        for j in range(i+1,6): c.append(ProvenanceConstraint(f'e{i}',f'e{j}',Relation.DISTINCT,'seed',True))
    for j in [1,2,3,4,5]: c.append(ProvenanceConstraint('e6',f'e{j}',Relation.DISTINCT,'seed',True))
    for j in [0,2,3,4,5]: c.append(ProvenanceConstraint('e7',f'e{j}',Relation.DISTINCT,'seed',True))
    actions=[
      Action('route','routing',.02,('A','B')),
      Action('critical_A','relation',.20,('SAME_ROOT','DISTINCT_ROOT'),'e0','e6'),
      Action('critical_B','relation',.20,('SAME_ROOT','DISTINCT_ROOT'),'e1','e7')]
    worlds=[
      World('A_is_decisive',.5,(('route','A'),('critical_A','DISTINCT_ROOT'),('critical_B','SAME_ROOT'))),
      World('B_is_decisive',.5,(('route','B'),('critical_A','SAME_ROOT'),('critical_B','DISTINCT_ROOT')))]
    return events,c,actions,worlds

def complementarity_scenario(p=.8):
    events=[EvidenceEvent(f'e{i}',f's{i}',1) for i in range(7)]
    c=[]
    for i in range(5):
        for j in range(i+1,5): c.append(ProvenanceConstraint(f'e{i}',f'e{j}',Relation.DISTINCT,'seed',True))
    for j in [1,2,3,4,6]: c.append(ProvenanceConstraint('e5',f'e{j}',Relation.DISTINCT,'seed',True))
    for j in [0,2,3,4,5]:
        pair=tuple(sorted(('e6',f'e{j}')))
        if not any(tuple(sorted((x.left,x.right)))==pair for x in c):
            c.append(ProvenanceConstraint('e6',f'e{j}',Relation.DISTINCT,'seed',True))
    actions=[Action('probe_A','relation',.05,('SAME_ROOT','DISTINCT_ROOT'),'e0','e5'),Action('probe_B','relation',.05,('SAME_ROOT','DISTINCT_ROOT'),'e1','e6')]
    worlds=[]
    for oa,pa in [('DISTINCT_ROOT',p),('SAME_ROOT',1-p)]:
        for ob,pb in [('DISTINCT_ROOT',p),('SAME_ROOT',1-p)]:
            worlds.append(World(oa[0]+ob[0],pa*pb,(('probe_A',oa),('probe_B',ob))))
    return events,c,actions,worlds
