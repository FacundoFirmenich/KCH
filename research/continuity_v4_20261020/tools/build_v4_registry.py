#!/usr/bin/env python3
"""Assemble additive claims and correction status; does not adjudicate tests."""
import argparse, copy, hashlib, json, os
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, data): p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',type=Path,required=True); a=ap.parse_args()
    repo=a.repo.resolve(); root=repo/'research/continuity_v4_20261020'; parent=repo/'research/continuity_v3_20261013'
    old=json.loads((parent/'CLAIM_EVIDENCE_REGISTRY.json').read_text()); registry=copy.deepcopy(old)
    registry.update(format='KCH_INTEGRAL_CLAIM_EVIDENCE_REGISTRY_V4',date='2026-10-20',
      role='Additive review implementation, exact finite comparison and operational interpretation',
      parent_registry_sha256=sha(parent/'CLAIM_EVIDENCE_REGISTRY.json'),
      update_scope='Complete V6 manuscripts; frozen real-instance greedy baseline; structural ECH module; solar clocks; M33 nullity; twelve domains retained.',
      no_hhc=True, new_observations=False, inherited_claims_unchanged=len(old['claims']))
    for source in registry['sources']:
        if source.get('local_path'):
            previous=source['local_path']; source['local_path']=os.path.relpath((parent/previous).resolve(),root)
            if source.get('uri')==previous: source['uri']=source['local_path']
    sources={
      'P1V6':'papers/PAPER_1_TASK_RELATIVE_STATE_SUFFICIENCY_V6.md',
      'P2V6':'papers/PAPER_2_CONDITIONAL_AXIAL_TRANSPORT_LIMITS_V6.md',
      'P1RETENTION':'papers/PAPER_1_V6_RETENTION_MAP.json',
      'P2RETENTION':'papers/RETENTION_EMPIRICAL_V6.json',
      'GREEDY_PROTOCOL':'evidence/ech_comparison/PROTOCOL_GREEDY_V1.json',
      'GREEDY_RESULT':'evidence/ech_comparison/GREEDY_COMPARISON_RESULT.json',
      'GREEDY_CHECK':'evidence/ech_comparison/GREEDY_INDEPENDENT_CHECK.json',
      'GREEDY_LOCAL':'evidence/ech_comparison/GREEDY_JURISDICTIONS.json',
      'ECH_STRUCTURE':'theory/ECH_STRUCTURAL_CONTRIBUTION.md',
      'PHYSICAL_AUDIT':'evidence/physical_contracts/PHYSICAL_CONTRACT_AUDIT.json',
      'SOLAR_CONTRACT':'evidence/physical_contracts/SOLAR_OPERATIONAL_CONTRACT_ES.md',
      'M33_CONTRACT':'evidence/physical_contracts/M33_IDENTIFIABILITY_CONTRACT_ES.md',
      'DAVE_SEARCH':'evidence/physical_contracts/DAVE_SOURCE_SEARCH.json'}
    for identifier,path in sources.items():
        registry['sources'].append(dict(id=identifier,title=Path(path).stem,uri=path,local_path=path,sha256=sha(root/path)))
    def claim(identifier,domain,statement,status,sources,depends,reservations,next_action,prohibited):
        registry['claims'].append(dict(id=identifier,domain=domain,statement=statement,status=status,sources=sources,depends_on=depends,reservations=reservations,next_admissible_action=next_action,prohibited_inferences=prohibited,new_authority_granted=False))
    claim('FORMAL_V6_POSITIONING','formal','V6 sitúa suficiencia relativa a tarea frente a estados causales, PSR y abstracción; prueba especialización ECH bajo condiciones, preservando el cuerpo V5 reconstruible.',
      'COMPLETE_ADDITIVE_MANUSCRIPT_WITH_RETENTION',['P1V6','P1RETENTION'],['OBSERVATION_QUOTIENT','ECH_PLANNING_QUOTIENT'],['SUFFICIENCY_NOT_MINIMALITY','GENERAL_ABSTRACTION_NOT_NEW'],
      'Delimitar y demostrar una ventaja diferencial frente al antecedente más cercano.',['Una redacción más precisa demuestra novedad o aceptación editorial.'])
    claim('SEISMIC_V6_ESTIMAND','seismic','V6 precisa ganancia de log-score axial por hijo condicionada al evento y metadatos; conserva íntegros V5 y terminal negativo.',
      'CONDITIONAL_ESTIMAND_AND_COMPLETE_RETENTION',['P2V6','P2RETENTION'],['SEISMIC_TERMINAL_V11'],['EXECUTED_DENSITY_AND_BOOTSTRAP_AUDIT_PENDING','MARGINAL_COVERAGE_ASSUMED_NOT_REPROVED'],
      'Recuperar densidad ejecutada, normalización, pérdidas pareadas y configuración del bootstrap.',['El log-score condicional demuestra capacidad de predecir ocurrencias o acota helicidad física.'])
    claim('ECH_GREEDY_FIXED_ROUTES','ech','Greedy congelado antes de ejecución: 46/46 factibles, 15 óptimos conjuntos y 31 excesos; máximo 3. Frente al histórico: 2 mejores, 18 iguales, 26 peores. Checker independiente PASS.',
      'INDEPENDENTLY_VERIFIED_REAL_ARCHIVED_FINITE_COMPARISON',['GREEDY_PROTOCOL','GREEDY_RESULT','GREEDY_CHECK','GREEDY_LOCAL'],['ECH_JOINT_FIXED_ROUTES'],['RETROSPECTIVE_DEVELOPMENT','ALGORITHM_AND_FUTURE_INFORMATION_DIFFER','SINGLE_KERNEL_NOT_EXTERNAL_VALIDATION','TIMING_NOT_CONTROLLED_BENCHMARK'],
      'Equiparar información futura entre políticas y evaluar otro kernel real con protocolo fijado.',['Los 31 excesos se deben exclusivamente a no anticipar.','Hay ventaja universal, garantía de aproximación o de velocidad.'])
    claim('ECH_COST_DECOMPOSITION','ech','A−J=(A−R)+(R−J), donde R restringe a primeras etapas mínimas; el catálogo archivado tiene R=J en 46 rutas. El módulo explicita condiciones estructurales y cociente suficiente.',
      'CONDITIONAL_ANALYTIC_CHARACTERIZATION_WITH_FINITE_INSTANTIATION',['ECH_STRUCTURE','ECH_LOOKAHEAD_CATALOG'],['ECH_LOCAL_MINIMUM_LOOKAHEAD','ECH_PLANNING_QUOTIENT'],['BELLMAN_AND_DOMINANCE_PRINCIPLES_STANDARD','FINITE_EQUALITY_NOT_UNIVERSAL'],
      'Probar alcance de condiciones fuera del catálogo y separar anticipación de la regla de decisión.',['Toda instancia siempre tiene solución conjunta óptima con primera etapa mínima.'])
    claim('SOLAR_V4_CLOCK_CONTRACT','solar','Dos de tres folds LOHO ajustan con regiones de años posteriores al test; G usa actividad del extremo final y selección de cinco snapshots completos usa metadatos futuros. Resultados locales 4/7/5/0 conservados.',
      'VERIFIED_RETROSPECTIVE_OPERATIONAL_INTERPRETATION',['PHYSICAL_AUDIT','SOLAR_CONTRACT'],['SOLAR_TEMPORAL_V16','SOLAR_LOCAL_DIAGNOSTIC'],['NOT_CHRONOLOGICAL_REPLAY','G_RECONSTRUCTION','NO_NEW_VALIDATION'],
      'Definir emisión y disponibilidad de entradas, parámetros y elegibilidad antes de un replay cronológico nuevo.',['Se validó un pronóstico histórico emitido en 2011 o 2013.','La auditoría temporal incumple o invalida por sí sola el protocolo retrospectivo.'])
    claim('DAVE_ORIGINAL_SOURCE_AVAILABILITY','solar','La búsqueda documentada en 108 archivos recuperados y 51 miembros de ZIP no recupera la implementación original suficiente del gate DAVE v1.3.',
      'SOURCE_BLOCKER_WITH_BOUNDED_SEARCH',['DAVE_SEARCH','SOLAR_CONTRACT'],['SOLAR_FLUX'],['SEARCH_NOT_WHOLE_ACCOUNT_OR_WORLD','INTERNAL_DERIVATIVE_VS_MOSAIC_NOT_ADJUDICATED'],
      'Recuperar versión, código y entradas de la ejecución original y distinguir residuos internos del mosaico.',['No existe código original en ningún lugar.','El error del gate DAVE ya fue demostrado o corregido.'])
    claim('M33_OPERATOR_NULLITY','galactic_mhd','El operador radial archivado 2×3 tiene rango dos y nulidad uno; dirección normalizada aproximadamente (1,2,2)/3. Sus dos salidas no identifican tres coeficientes aun sin ruido.',
      'FIXED_ARCHIVED_OPERATOR_STRUCTURAL_NONIDENTIFICATION',['PHYSICAL_AUDIT','M33_CONTRACT','M33_REPLAY'],['M33_RADIAL'],['CONDITIONAL_FIXED_LINEAR_OPERATOR','NUISANCE_ADJUSTED_RANK_NOT_COMPUTED','LORENTZ_KERNEL_EQUIVALENCE_NOT_PROVED'],
      'Demostrar respuesta adicional no ortogonal al núcleo y separable de nuisance antes de adjudicar identificación 2D.',['La dirección aproximada publicada es exacta para todo operador físico.','La norma mínima puntual es una cota estadística o prueba de amplitud física.'])
    write(root/'CLAIM_EVIDENCE_REGISTRY.json',registry)
    corrections=[
      ('P0-01','Conservar corpus y manuscritos','IMPLEMENTED','108 archivos de entrada intactos; retención ejecutable de ambos V6.','Ninguno para esta obligación.'),
      ('P0-02','Reubicar novedad formal','IMPLEMENTED','Antecedentes próximos y alcance de suficiencia explícitos en PAPER1 V6.','Novedad diferencial y minimalidad siguen abiertas.'),
      ('P0-03','Precisar estimando sísmico y terminal','IMPLEMENTED','PAPER2 V6 terminal-first, marca axial condicional y límites estadísticos.','Auditoría computacional de densidad y bootstrap pendiente.'),
      ('P0-04','Comparador algorítmico ECH real','IMPLEMENTED_AND_INDEPENDENTLY_VERIFIED','Greedy congelado, 46 rutas completas, testigos y checker independiente.','Información futura no equiparada; un solo kernel.'),
      ('P0-05','Contrato temporal solar','IMPLEMENTED_AND_VERIFIED','G, LOHO y selección completa de ventanas delimitados; ganancias locales conservadas.','Replay cronológico nuevo no ejecutado.'),
      ('P0-06','Identificación M33','IMPLEMENTED_FOR_ARCHIVED_OPERATOR','Rango, núcleo, covarianzas y norma puntual distinguidos.','Puente físico y rango con nuisance pendientes.'),
      ('P0-07','Recuperar ejecución DAVE v1.3','BLOCKED_BY_SOURCE_IN_INSPECTED_CORPUS','Búsqueda con inventario y contratos de diagnóstico.','Código original e inputs no recuperados en el corpus inspeccionado.'),
      ('P0-08','Auditar densidad sísmica ejecutada','DOCUMENTED_NOT_EXECUTED','Fórmula, normalización, clipping y dependencias necesarios están especificados.','Requiere fuente ejecutada y pérdidas por unidad.'),
      ('P1-01','Separar mecanismos ECH','IMPLEMENTED_ANALYTIC_AND_FINITE','Descomposición A−J y caracterización condicionada; catálogo R=J conservado.','No theorem de equivalencia universal ni comparación causal de anticipación.'),
      ('P1-02','Generalización ECH','NOT_EXECUTED','Frontera explícita y prohibición de extrapolar tasas del catálogo.','Otro kernel real y comparación con información equiparada.'),
      ('P1-03','Prueba solar cronológica','NOT_EXECUTED','Contrato operacional especifica entradas y timestamps requeridos.','Nuevo protocolo y observaciones/partición no elegidas con resultados.'),
      ('P1-04','M33 2D y 75 sensibilidades','NOT_EXECUTED','Protocolo existente conservado; condición para romper núcleo identificada.','Datos adjudicables, operador físico y nuisance.'),
      ('P1-05','Conservar doce ramas','IMPLEMENTED','34 claims anteriores intactos y siete nuevos, con fuentes y dependencias.','Brechas específicas permanecen por rama, sin contaminación automática.'),
      ('P1-06','Despliegue de revisión reproducible','IMPLEMENTED_DRAFT_BRANCH','PR37, hashes de fuentes, manifiesto y CI con recibos nuevos.','No merge ni promoción canónica; PASS no equivale a validación científica global.')]
    ledger=dict(schema='KCH_SCIENTIFIC_CORRECTION_LEDGER_V4',date='2026-10-20',no_hhc=True,all_gaps_closed=False,new_observations=False,
      review_basis='Review 2026-10-20; broad targeted literature analysis with declared read depths, not exhaustive census.',
      parent_claims_preserved=34,new_claims=len(registry['claims'])-34,
      corrections=[dict(id=i,obligation=o,status=s,implemented=e,remaining=r) for i,o,s,e,r in corrections],
      original_review_P0_crosswalk=[
        dict(obligation='Contribution/predecessor matrix',artifact='CONTRIBUTION_MATRIX_ES.md',status='IMPLEMENTED_WITH_OPEN_NOVELTY_DELTA'),
        dict(obligation='Operational language',artifact='CONTRIBUTION_MATRIX_ES.md',status='IMPLEMENTED_WITH_EXPLICIT_PHYSICAL_GAPS'),
        dict(obligation='Evidence units',artifact='CONTRIBUTION_MATRIX_ES.md',status='IMPLEMENTED_NOT_A_NEW_DEPENDENCE_ANALYSIS'),
        dict(obligation='Corpus reservations',artifact='CLAIM_EVIDENCE_REGISTRY.json',status='PRESERVED_AND_EXTENDED'),
        dict(obligation='Version synchronization',artifact='CONTRIBUTION_MATRIX_ES.md',status='IMPLEMENTED_WITH_PRIOR_BYTES_UNCHANGED')],
      required_domains=registry['required_domains'],
      publication_readiness='Improved reviewability; no acceptance, novelty, power or identifiability score is promoted merely by editorial changes.')
    write(root/'SCIENTIFIC_CORRECTION_LEDGER.json',ledger)
    print(json.dumps(dict(claims=len(registry['claims']),sources=len(registry['sources']),domains=len(registry['required_domains']),corrections=len(corrections))))

if __name__=='__main__': main()
