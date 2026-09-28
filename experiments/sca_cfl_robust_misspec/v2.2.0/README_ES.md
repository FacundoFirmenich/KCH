# SCA/CFL Robust Adaptive Intervention under Model Misspecification v2.2.0

Gate `ROBUST_ADAPTIVE_INTERVENTION_UNDER_MODEL_MISSPECIFICATION_013`.

La clase operacional son cinco rectángulos disjuntos de radio 0.10 alrededor de firmas L/M/H en dos intervenciones. Cada coordenada usa una confidence sequence obtenida por inversión de un e-process Jeffreys/Beta(1/2,1/2). Una certificación exige cierre compatible en ambas coordenadas. Una combinación cruzada o una coordenada fuera de todas las bandas produce `MODEL_CLASS_BREAK`; evidencia insuficiente produce `HOLD_UNRESOLVED`.

Campaña: 5,000 episodios legales con 0 certificaciones incorrectas y 0 falsos breaks; 44 HOLD. 4,000 splices estructurados con break medio 99.625% y 0 falsas certificaciones. El parent v2.1 certifica alguna hipótesis del catálogo en 100% de esos splices. Control continuo p=(0.30,0.70): 76% break, 24% HOLD, 0 certificaciones falsas.
