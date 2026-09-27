from .partitions import enumerate_partitions

def partition_e_value(comps,partition,p0=.5,p1=.8):
    e=1.0
    for block in partition:
        dirs=set()
        for i in block: dirs.update(comps[i]["directions"])
        if dirs=={1}: e*=p1/p0
        elif dirs=={-1}: e*=(1-p1)/(1-p0)
        elif dirs=={1,-1}: e*=1.0
        else: raise ValueError("BAD_DIRECTION")
    return e

def robust_genealogy_gate(events,constraints,threshold=20.0,max_components=10):
    comps,parts=enumerate_partitions(events,constraints,max_components=max_components)
    vals=[partition_e_value(comps,p) for p in parts]
    robust=min(vals) if vals else 1.0
    naive=(1.6**sum(e.direction==1 for e in events))*(0.4**sum(e.direction==-1 for e in events))
    return {"robust_e_value":robust,"naive_e_value":naive,"admissible_partitions":len(parts),"eligible":robust>=threshold}
