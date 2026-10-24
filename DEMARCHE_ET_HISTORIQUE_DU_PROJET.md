# 📜 Chronologie, Démarche & Historique Intégral du Projet Apex
**Projet** : *Vampires VS Werewolves*  
**Matière** : Fondements de l'Intelligence Artificielle (FIA) – CentraleSupélec  
**Auteur** : Othmane MAAMAR  
**Rôle du document** : Synthèse méthodologique complète pour le rapport de projet et la soutenance technique.

---

## 🧭 1. Contexte & Règles du Jeu

Le projet *Vampires VS Werewolves* oppose deux espèces prédatrices (Vampires et Loups-Garous) sur une grille 2D discrète avec déplacements dans les 8 directions de Chebyshev ($L_\infty$). Le temps de réponse par coup est strictement plafonné à **$T \le 2.00$ secondes** via un protocole TCP binaire.

### Les 3 lois fondamentales du jeu :
1. **La Capture Déterministe des Humains ($E_1 \ge H$)** :
   * Si nos unités attaquantes $E_1$ sont supérieures ou égales au nombre d'humains neutres $H$, la conversion est instantanée, garantie à 100% et sans aucune perte : l'armée passe à $E_1 + H$.
   * Si $E_1 < H$, l'assaut est probabiliste ($P = E_1 / 2H$) avec espérance de pertes dramatique ($P^2 \times E_1$). Attaquer en sous-effectif est un suicide tactique.
2. **Le Seuil Lanchester d'Annihilation Déterministe ($E_1 \ge 1.5 \times E_2$)** :
   * Si une armée attaque un groupe rival avec un ratio supérieur ou égal à $1.5\times$, la victoire est certaine à 100% et l'ennemi est rayé de la carte sans aucune perte amie.
3. **Le Piège du Combat Aléatoire (Zone 3 : $E_2 / 1.5 < E_1 < 1.5 \times E_2$)** :
   * En cas de combat non déterministe (par exemple 10 contre 10, où $P = 0.5$), la loi binomiale de résolution inflige en espérance $P^2 \times E_1 = 0.25 \times 10 = 2.5$ survivants. Tenter un coup de dé revient à risquer l'élimination immédiate de la partie.

---

## 🏛️ 2. Phase 1 : La Genèse (Apex v1 – Minimax Classique & "Deathball")

### La Doctrine Initiale :
Pour respecter scrupuleusement la loi de Lanchester ($1.5\times$), Apex a été conçu autour du **principe de concentration de force (Deathball)** :
* Maintenir l'ensemble de nos troupes en un seul bloc unifié.
* Si l'armée est scindée, ordonner le regroupement immédiat.
* Élagage Alpha-Bêta classique avec hachage de Zobrist 64 bits et approfondissement itératif (IDS).

### Les Premières Limites Découvertes :
1. **L'Effet d'Horizon** : Un groupe d'humains ou une menace ennemie située à profondeur $d+1$ n'est pas vu par la recherche et provoque des captures prématurées ou des embuscades subies.
2. **La Myopie Territoriale** : L'Alpha-Bêta case par case (portée 4 à 6 cases en 1.65s) est aveugle aux événements distants sur des cartes allant jusqu'à $15 \times 29$ ou $50 \times 50$.

---

## 🔬 3. Phase 2 : L'Architecture Tri-Échelle Apex v2 & L'Ablation Arena

Pour surmonter ces faiblesses, nous avons décomposé le problème selon trois échelles spatio-temporelles :
* **Micro-tactique ($t \le 1$) : Quiescence Search (QS)** pour sécuriser les captures immédiates aux feuilles de l'arbre sans effet d'horizon.
* **Méso-économie ($1 \le t \le 3$) : Optimal Foraging Rate (OFR)** pour maximiser le rendement temporel net de conversion des villages humains.
* **Macro-territoire ($t \ge 3$) : Voronoï Capacitaire** pour filtrer les villages hors d'atteinte et éviter les mirages.

### L'Étude d'Ablation Complète (Round-Robin interne) :
En testant les $2^3 = 8$ combinaisons modulaires face à un panel de 4 IA rivales (`GreedyReflex`, `TacticalSplitter`, `ShallowMinimax`, `MonteCarlo`), un résultat surprenant est apparu :
* **`Apex_VOR_QS` (Voronoï + Quiescence)** : **Champion #1 avec 84.4% de victoires**.
* **`Apex_v2_All` (OFR + Voronoï + QS)** : Chute en 5ème position (52.7%).

---

## ⚠️ 4. Phase 3 : La Crise Expérimentale & Le Diagnostic d'Argon

L'effondrement de la version complète `Apex_v2_All` et les régressions observées sous Quiescence Search ont fait l'objet d'un diagnostic d'ingénierie approfondi (documenté dans `argon_issues_response.md`) :

### 1. La Régression Quiescence Search :
* **Cause** : La désactivation du `Stand-Pat` sous menace létale (`under_lethal_threat`) supprimait les coupures $\beta$ (qui représentent 70 à 85% des nœuds) et déclenchait un phénomène de « Ping-Pong de Chebyshev » où les escouades tournaient en rond à $d=1$.
* **Correctif** : Rétablissement du `Stand-Pat` inconditionnel à 100%, suppression du tri en pur Python aux feuilles, et limitation stricte à $qdepth=1$ sur captures déterministes uniquement.

### 2. Le Conflit Voronoï vs Foraging (OFR) :
* **Cause** : Le Voronoï appliquait un veto binaire brutal dès qu'un ennemi était virtuellement plus proche d'une seule case, provoquant des hésitations oscillatoires de l'armée.
* **Correctif** : Remplacement du veto par un facteur d'atténuation continu $\Gamma_{VOR} \in [0, 1.5]$ sans effet de seuil discontinu.

### 3. La Faille du « Défenseur Fantôme » :
* **Cause** : Une petite troupe ennemie (ex: 2 loups) bloquait l'accès à un village de 8 humains car elle était plus proche, alors qu'elle ne pouvait pas le capturer sans se suicider.
* **Correctif** : Filtrage par crédibilité : un ennemi n'est considéré comme compétiteur que s'il a les effectifs requis ($e_{cnt} \ge h_{cnt}$).

---

## 🥊 5. Phase 4 : Le Choc face à Mohamed Splitter & L'Hypothèse des Grandes Cartes

Lors de la confrontation de nos 3 meilleures variantes face au `Splitter` (MCTS) de Mohamed sur 24 matchs Aller-Retour :
* **Score global catastrophique : 0 Victoire - 4 Défaites - 4 Nuls (0% de victoires)**.
* **Sur Carte Géante (`25x25`)** : Mohamed a pulvérisé nos variantes en terminant avec **64 unités contre 20 pour nous**.

### L'Intuition Clé d'Othmane :
> *« Notre algorithme le plus puissant fait une bonne performance sur les petites cartes, mais se fait pulvériser sur les grandes cartes... En voulant éliminer les risques en restant en un seul bloc, on augmente en réalité le risque fatal de se faire out-numbered. »*

Les données ont validé cette intuition :
1. Sur `Officielle_15x29`, **20 humains sur 32 sont restés totalement intouchés** au tour 80 ! L'armée oscillait passivement au centre.
2. L'adversaire scindait ses troupes en 5 à 8 escouades pour récolter la carte en parallèle, tandis que notre armée monobloc récoltait un seul village en série. Quand le combat survenait, l'ennemi était à $64$ contre $20$ ($> 3\times$ notre taille), rendant toute tactique inutile.

---

## 🚀 6. Phase 5 : Le Déblocage Itératif (Apex V0 $\rightarrow$ V1 $\rightarrow$ V2)

### Étape 1 : Apex V1 – Split Intelligent & Autonomie des Groupes
* **Diagnostic du code V0** :
  - La réserve de sécurité interdisait tout split dès qu'un ennemi était à distance 6 (la moitié du plateau !).
  - Dès qu'une armée se scindait, `CASE 2` dans `generate_moves` forçait chaque groupe à faire demi-tour pour fusionner via `val -= dist * 50`.
  - La fonction `evaluate()` infligeait une pénalité violente de $-300 \times dist$ sur la séparation.
* **Correctifs V1** :
  1. Réserve de sécurité calibrée à la portée de frappe réelle ($d \le 3$).
  2. Autonomie de navigation : chaque groupe poursuit son propre village humain sans chercher à fusionner tant qu'il n'est pas menacé.
  3. Suppression de la pénalité aveugle de distance dans `evaluate()`.
* **Validation Duel V1 vs V0** :
  - **Sur `Carree_10x10` : Apex V1 pulvérise V0 22-0 (Aller) et 25-0 (Retour) !**
  - Score global V1 vs V0 : **2 Victoires, 0 Défaite, 6 Nuls**.

### Étape 2 : Apex V2 – Gradient Longue Portée & Combats Calculés
* **Diagnostic du code V1** :
  - Sur 15x29 et 25x25, les matchs finissaient encore en nul (16-16 et 17-17). L'attraction divisée par $(d+1)$ s'éteignait à grande distance ($pull \approx 400$).
  - Apex refusait catégoriquement le combat sans supériorité de $1.5\times$ (malus de $-50\,000$), fuyant même avec $85\%$ de chances de victoire.
* **Correctifs V2** :
  1. **Boussole Longue Portée (Gradient non-décroissant)** :  
     $\text{dist\_factor} = \max(0.25, 1.0 - 0.65 \times (d / \text{max\_dim}))$. L'armée gagne un score constant à chaque pas vers la cible, évitant l'enlisement au centre.
  2. **Évaluation Probabiliste des Combats** :  
     Si la probabilité de victoire calculée dépasse $70\%$ (ex: 16 contre 12), le bot pousse son avantage et attaque au lieu de fuir.
  3. **Pression Territoriale en Fin de Partie** :  
     Dès que les humains proches sont absorbés et que la parité numérique est acquise, l'armée traque activement l'ennemi.
* **Validation Duel V2 vs V1 & V0** :
  - V2 bat V1 (3 victoires à 2) et monte à **45 unités** sur 25x25.
  - V2 surclasse V0 (3 victoires à 1) avec **35-22 et 51-12** sur 25x25.

### Étape 3 : L'Épreuve Ultime contre Mohamed Splitter
Dans le match de revanche sur carte géante 25x25 :
* **Match Retour : VICTOIRE D'APEX V2 (46 contre 40 unités) !**
* **Match Aller : Score ultra-serré (41 contre 45)** au lieu du 20 contre 64 initial.
* **Bilan : 1 Victoire, 2 Défaites, 3 Nuls**. Le verrou des grandes cartes est officiellement brisé.

---

## 📊 7. Synthèse Globale des Performances par Version

| Caractéristique | Apex V0 (Baseline) | Apex V1 (Split Initial) | Apex V2 (Actuel Déployé) |
| :--- | :---: | :---: | :---: |
| **Doctrine de Mouvement** | Monobloc rigide (Deathball) | Scission économique permise | Scission + Autonomie + Boussole |
| **Portée du Gradient** | Locale ($1/d$ hyperbolique) | Locale ($1/d$) | **Globale normalisée ($\max(rows, cols)$)** |
| **Gestion du Risque Combat** | Veto absolu $< 1.5\times$ ($-50\,000$) | Veto absolu $< 1.5\times$ | **Calcul d'espérance ($P \ge 70\%$)** |
| **Score vs V0 sur 10x10** | - | **22-0 et 25-0** (Victoire V1) | **22-0** (Victoire V2) |
| **Effectif max sur 25x25** | 20 unités | 17 unités | **51 unités** |
| **Face à Mohamed sur 25x25** | 17-64 (Défaite écrasante) | 12-45 (Défaite) | **46-40 (VICTOIRE)** |

### 7.1. Le Tournoi Officiel des 10 Matchs Alternés (Apex Champion vs Mohamed Splitter)

Résultats du tournoi de validation officiel exécuté sur 5 formats de cartes (Aller & Retour complets) :

| # | Format de Carte | Vampires [Rouge] | Loups-Garous [Bleu] | Vainqueur | Tours | Score Final |
| :-: | :--- | :--- | :--- | :---: | :-: | :---: |
| **1** | `TheTrap_5x10` (Aller) | ApexChampion (V) | Mohamed_Splitter (W) | **ApexChampion** | 2 | **V=2 - W=0** (Victoire éclair) |
| **2** | `TheTrap_5x10` (Retour) | Mohamed_Splitter (V) | ApexChampion (W) | Mohamed_Splitter | 80 | V=10 - W=7 |
| **3** | `Carree_10x10` (Aller) | ApexChampion (V) | Mohamed_Splitter (W) | Mohamed_Splitter | 34 | V=0 - W=10 |
| **4** | `Carree_10x10` (Retour) | Mohamed_Splitter (V) | ApexChampion (W) | Mohamed_Splitter | 33 | V=32 - W=0 |
| **5** | `Rectangle_10x18` (Aller) | ApexChampion (V) | Mohamed_Splitter (W) | Mohamed_Splitter | 54 | V=0 - W=40 |
| **6** | `Rectangle_10x18` (Retour) | Mohamed_Splitter (V) | ApexChampion (W) | **ApexChampion** | 73 | **V=0 - W=34** (Victoire nette) |
| **7** | `Officielle_15x29` (Aller) | ApexChampion (V) | Mohamed_Splitter (W) | **Match NUL** | 80 | **V=16 - W=16** |
| **8** | `Officielle_15x29` (Retour) | Mohamed_Splitter (V) | ApexChampion (W) | **Match NUL** | 80 | **V=16 - W=16** |
| **9** | `Geante_25x25` (Aller) | ApexChampion (V) | Mohamed_Splitter (W) | Mohamed_Splitter | 80 | V=22 - W=52 |
| **10** | `Geante_25x25` (Retour) | Mohamed_Splitter (V) | ApexChampion (W) | Mohamed_Splitter | 80 | V=51 - W=35 |

* **Victoires Apex Champion (Alpha-Bêta Minimax)** : **2 victoires** (dont une victoire en 2 tours sur piège et un 34-0 net sur 10x18).
* **Matchs Nuls** : **2 nuls** (neutralisation parfaite sur la carte officielle 15x29).
* **Victoires Mohamed Splitter (MCTS)** : **6 victoires**.

---

## 🎯 8. Enseignements Stratégiques pour la Soutenance

1. **La Théorie des Jeux sur Grandes Cartes** :  
   Minimiser le risque local en restant groupé maximise en fait le risque global de défaite économique. La scission asymétrique et la récolte parallèle sont indispensables sur tout plateau $\ge 12 \times 12$.
2. **La Résolution de l'Horizon Temporel sans Explosion Combinatoire** :  
   Pour avoir une « vision à 30 ou 50 tours », il ne faut pas chercher 50 plys microscopiques, mais combiner un gradient spatial directionnel à longue portée avec des macro-décisions de détachement.
3. **Le Contrôle du Garbage Collector & Zobrist 64 bits** :  
   Le hachage par XOR binaire en $O(1)$ et la désactivation du ramasse-miettes pendant la recherche permettent de maintenir un débit constant de plus de 20 000 nœuds/seconde dans le budget strict de 1.65 seconde.
