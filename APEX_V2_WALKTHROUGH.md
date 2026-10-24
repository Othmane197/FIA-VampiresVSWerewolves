# 🐺 Architecture & Fonctionnement Intégral du Moteur Apex v2 (Guide Technique)
**Projet** : Vampires VS Werewolves (FIA – CentraleSupélec)  
**Auteur** : Équipe Apex (Othmane MAAMAR)  
**Document de Référence** : Rapport d'architecture, modélisation mathématique et soutenance technique

---

## 🏛️ 1. Vue d'Ensemble & Philosophie du Moteur

Le projet *Vampires VS Werewolves* pose un défi combinatoire et stochastique à contrainte temps-réel stricte (**T ≤ 2.00 s par coup** via socket TCP). 

L'architecture **Apex v2** a été conçue pour résoudre les faiblesses traditionnelles des moteurs Minimax classiques (l'effet d'horizon, la myopie territoriale, et la vulnérabilité aux combats aléatoires) en articulant la décision selon une **décomposition tri-échelle cohérente** :

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE DE DÉCISION APEX V2                                │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
        ┌───────────────────────────────────┼───────────────────────────────────┐
        ▼                                   ▼                                   ▼
┌───────────────────────┐       ┌───────────────────────┐       ┌───────────────────────┐
│     MICRO-TACTIQUE    │       │     MÉSO-ÉCONOMIE     │       │    MACRO-TERRITOIRE   │
│   Quiescence Search   │       │Optimal Foraging Rate  │       │  Voronoï Capacitaire  │
│       (t ≤ 1)         │       │     (1 ≤ t ≤ 3)       │       │       (t ≥ 3)         │
└───────────────────────┘       └───────────────────────┘       └───────────────────────┘
        │                                   │                                   │
        ▼                                   ▼                                   ▼
Élimine l'effet d'horizon      Maximise le rendement           Neutralise les mirages
et sécurise les contacts à     temporel net de conversion      et pondère par la capacité
distance 1 (anti-embuscade)    des colonies adjacentes         crédible de l'adversaire
```

---

## ⚔️ 2. Modélisation Mathématique des Combats & Règles du Jeu

Dans *Vampires VS Werewolves*, les unités se déplacent sur une grille 2D dans les 8 directions (distance de Chebyshev) :
```text
Distance(A, B) = max( |x_A - x_B|, |y_A - y_B| )
```
Chaque déplacement sur une case occupée déclenche une résolution immédiate.

---

### 2.1. Capture des Humains Neutres

Soit **E1** le nombre de monstres attaquants arrivant sur une case contenant **H** humains :

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ • Si E1 ≥ H  ───>  Capture Déterministe : Pertes = 0, Armée finale = E1 + H (100% gain) │
│ • Si E1 < H  ───>  Combat Aléatoire     : Probabilité de Victoire = E1 / (2 × H)        │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 📖 En clair :
* **Cas Déterministe (E1 ≥ H) :** Si nous avons au moins autant de monstres que d'humains (ex: 5 vampires contre 3 humains), la conversion est garantie à 100% sans aucune perte. Notre armée passe instantanément à **5 + 3 = 8 monstres**.
* **Cas Aléatoire (E1 < H) :** Si nous attaquons en sous-effectif (ex: 2 monstres contre 4 humains), la probabilité de victoire n'est que de **2 / (2 × 4) = 25%**. Même en cas de victoire improbable, les survivants subissent des pertes massives.
* **Règle absolue pour l'IA :** Attaquer un village avec E1 < H est une action strictement interdite (suicide tactique).

---

### 2.2. Combat entre Espèces Rivales (Vampires vs Loups-Garous)

Soit **E1** le nombre d'attaquants et **E2** le nombre de défenseurs :

```text
        ZONE 1 :                     ZONE 3 :                     ZONE 2 :
    Défaite Certaine             Combat Aléatoire             Victoire Certaine
   (Attaquants anéantis)       (Résolution probabiliste)     (Défenseurs anéantis)
 <-----------------------]-----------------------------------[----------------------->
 0                   E2 / 1.5                             1.5 * E2                  E1
```

La probabilité **P** que l'attaquant gagne le combat est définie par :

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Probabilité de Victoire de l'attaquant P(E1) :                                         │
│                                                                                        │
│ • Si E1 ≥ 1.5 × E2  ───>  100% (P = 1.0)       [Zone 2 : Victoire Certaine, 0 perte]   │
│ • Si E1 = E2        ───>   50% (P = 0.5)       [Zone 3 : Égalité parfaite]             │
│ • Si E1 < E2        ───>  E1 / (2 × E2)        [Zone 3 : Sous-effectif]                │
│ • Si E1 > E2        ───>  (E1 / E2) - 0.5      [Zone 3 : Avantage insuffisant]         │
│ • Si E1 ≤ E2 / 1.5  ───>    0% (P = 0.0)       [Zone 1 : Défaite Certaine]             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 🎲 Résolution des pertes en cas de combat aléatoire (Zone 3) :
Si le combat est aléatoire et que l'attaquant gagne le premier tirage (probabilité P), chaque unité survivante subit ensuite un **deuxième tirage aléatoire** de probabilité P (loi binomiale).  
L'espérance mathématique du nombre d'unités survivantes est donc :

```text
Espérance(Survivants) = P × (P × E1) = P² × E1
```

#### 💡 Exemple concret : combat 10 contre 10 (E1 = 10, E2 = 10) :
* La probabilité de victoire est **P = 0.5** (une chance sur deux).
* L'espérance de survivants est : **0.5 × (0.5 × 10) = 0.25 × 10 = 2.5 unités**.
* **Conclusion tactique :** On a 50% de chance d'être éliminé de la partie sur un coup de dé, et même si on gagne, il ne nous reste en moyenne que 2 ou 3 survivants sur 10. **L'IA Apex fuit absolument la Zone 3 aléatoire et ne frappe que dans la Zone 2 (E1 ≥ 1.5 × E2).**

> [!IMPORTANT]
> **Le Principe de Concentration de Lanchester ("Deathball") :**  
> En raison du seuil 1.5×, regrouper nos troupes en un unique bloc compact crée une supériorité opérationnelle déterminante : aucune troupe adverse dispersée ne peut nous attaquer sans défaite déterministe.

---

## 🗺️ 3. Composant Macro : Le Voronoï Capacitaire (Capacity-Aware Voronoi)

### 3.1. Le Problème du "Défenseur Fantôme" (Ghost Defender)
Dans les implémentations naïves de Voronoï sur grille, un village H est abandonné dès que l'ennemi le plus proche est métriquement plus près que nous (`Distance_ennemi < Distance_nous`).  
* **L'erreur fatale de la version v1 :** Si 2 loups sont à distance 2 d'un village de 8 humains, et que nos 15 vampires sont à distance 3, le Voronoï standard abandonnait ce village ! Pourtant, les 2 loups ne peuvent **pas** capturer 8 humains sans un risque de suicide quasi certain (2 < 8).

---

### 3.2. Formule des Compétiteurs Réels (Élimination des Fantômes)

Un groupe ennemi n'est considéré comme une vraie menace que s'il a les effectifs nécessaires pour convertir le village sans risque :

```text
Compétiteurs Réels(H) = Ensemble des groupes ennemis 'e' ayant Effectif(e) ≥ Humains(H)
```

La distance de menace ennemie effective `Min_Distance_Ennemi(H)` devient :

```text
Min_Distance_Ennemi(H) =
  • Plus petite distance d'un compétiteur réel s'il en existe un
  • 99 (menace nulle) si aucun ennemi ne peut capturer le village
```

```text
EXEMPLE DU DÉFENSEUR FANTÔME RÉSOLU :
Village : 8 humains. Ennemi : 2 loups à d = 2. Notre armée : 15 vampires à d = 3.

• Voronoï naïf (v1) : d_ennemi = 2 < d_nous = 3 ───> Village abandonné ❌ (Grave erreur !)
• Voronoï Robuste   : L'ennemi (2 loups) ne peut pas convertir 8 humains (2 < 8).
                      Il est éliminé des compétiteurs. Distance ennemie = 99.
                      99 >> d_nous (3) ───> Village allié garanti ✅ (Ratio = 1.4)
```

---

### 3.3. Facteur Territorial Continu : Ratio_voronoi(H)

Pour éviter les à-coups brutaux (tout-ou-rien), chaque village reçoit un multiplicateur de sécurité :

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Multiplicateur Territorial Ratio_voronoi(H) :                                          │
│                                                                                        │
│ • 1.4 (+40% de bonus) : Si Distance_nous < Min_Distance_Ennemi                         │
│                         [Zone Sécurisée Alliée : arrière-pays protégé]                 │
│                                                                                        │
│ • 1.0 (Neutre)        : Si Distance_nous = Min_Distance_Ennemi                         │
│                         [Frontière de Course / Contestation directe]                   │
│                                                                                        │
│ • 1.0 (Neutre)        : Si Distance_nous > Min_Distance_Ennemi ET Armée_nous ≥ 1.5×Ennemi│
│                         [Écrasement Militaire Possible]                                │
│                                                                                        │
│ • 0.4 (-60% de malus) : Si l'ennemi est plus proche sans possibilité de l'écraser      │
│                         [Zone Défavorable Amortie : évite les courses vaines]          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🍎 4. Composant Méso : Théorie du Butinage Optimal (Optimal Foraging Rate - OFR)

### 4.1. Pourquoi la Formule OFR ?
Dans les versions antérieures, l'attraction d'un village utilisait la formule naïve `(N_humains^1.1) / (distance + 1)`.  
Cela créait le piège classique des **« longs pèlerinages »** : l'IA délaissait un groupe de 2 humains juste à côté (d = 1) pour courir pendant 6 tours vers un groupe de 8 humains lointain, laissant le temps à l'ennemi de dominer toute la carte.

Inspirée par la *Théorie du Butinage Optimal* (Charnov, écologie comportementale), la formule v2 calcule l'**attractivité nette immédiate** :

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           FORMULE D'ATTRACTION OFR                                     │
│                                                                                        │
│                             W_pull × N_humains × Ratio_voronoi                         │
│    Score_Attraction(H) =   ────────────────────────────────────  + Bonus_contact(d)    │
│                                       (d + 0.5)^1.6                                    │
│                                                                                        │
│    Avec Bonus_contact(d) =                                                             │
│      • +8000 points si d = 1  (le village est à portée d'1 seule case)                 │
│      •      0 point  si d > 1  (le village est à 2 cases ou plus)                      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 4.2. Décomposition Détaillée de Chaque Terme

| Terme | Nom | Rôle & Intuition | Valeur dans Apex |
| :--- | :--- | :--- | :--- |
| **W_pull** | Poids d'attraction | Multiplicateur pour mettre l'attraction à l'échelle de l'évaluation globale | `1500` |
| **N_humains** | Gain en ressource | Nombre d'humains convertibles dans le village | `1, 2, 3, etc.` |
| **Ratio_voronoi** | Sécurité territoriale | Coefficient issu du Voronoï capacitaire (1.4, 1.0 ou 0.4) | `0.4 à 1.4` |
| **d** | Distance | Distance de Chebyshev (nombre de coups pour atteindre la case) | `1, 2, 3, etc.` |
| **(d + 0.5)^1.6** | Décroissance temporelle | Pénalité supra-linéaire : un village à d=4 est 6.6 fois moins attractif qu'à d=1 | Exposant `1.6` |
| **+8000 si d=1** | Prime d'absorption immédiate | Manger un village en 1 coup gonfle nos effectifs dès le tour suivant (effet boule de neige) | `8000 pts` |

---

### 4.3. Exemples Chiffrés Pas-à-Pas

Comparons le choix de l'IA entre deux opportunités :

* **Village A (Proche mais modeste) :** 2 humains à distance d = 1, dans notre zone allié (Ratio = 1.4)
  ```text
  Score(A) = [ (1500 × 2 × 1.4) / (1 + 0.5)^1.6 ] + 8000
           = [ 4200 / 1.91 ] + 8000
           = 2199 + 8000
           = 10 199 points
  ```

* **Village B (Lointain mais alléchant) :** 8 humains à distance d = 4, en zone neutre (Ratio = 1.0)
  ```text
  Score(B) = [ (1500 × 8 × 1.0) / (4 + 0.5)^1.6 ] + 0
           = [ 12 000 / 11.08 ] + 0
           = 1 083 points
  ```

👉 **Résultat concret :** Le village adjacent A obtient un score **10 fois supérieur** (10 199 contre 1 083).  
L'IA absorbe immédiatement les 2 humains adjacents au lieu de perdre 4 tours à courir à travers la carte !

---

## 🛡️ 5. Composant Micro : Quiescence Search (Recherche de Repos Tactique)

### 5.1. Résolution de l'Effet d'Horizon
À profondeur depth = 0, un Minimax standard évalue statiquement la position. Si deux armées se trouvent au contact immédiat (d = 1), l'évaluation statique voit notre armée intacte et renvoie un score faussement optimiste, ignorant le fait qu'elle va se faire dévorer au coup suivant.

### 5.2. Principe du Stand-Pat & Détection d'Instabilité
À la feuille (depth = 0), l'algorithme teste s'il y a un contact direct avec l'ennemi :

```text
Position Instable (Non Quiescente)  <===>  Il existe une armée ennemie à distance d = 1
```

* **Si aucun contact (d > 1) :** la position est calme (**quiescente**), on renvoie directement l'évaluation statique `Evaluate(state)`.
* **Si contact présent (d = 1) :** la recherche s'étend récursivement sur un pli tactique additionnel (`qdepth = 1`) en ne testant que les captures décisives.

### 5.3. Le Stand-Pat : Élagage Ultra-Rapide
Avant d'explorer la moindre capture en Quiescence Search, on calcule le score de repos (**Stand-Pat**) :

```text
Stand_Pat = Evaluate(État actuel)

• Si Stand_Pat ≥ Beta  ───> Coupure Beta immédiate en O(1) (inutile d'explorer les coups)
• Si Stand_Pat > Alpha ───> Alpha = Stand_Pat
```

### 5.4. Élagage Radical : Captures Déterministes Uniquement
Pour garantir une exécution ultra-rapide en pur Python sans perte de profondeur globale :
1. **Zéro coup calme (quiet move) en QS** : Les déplacements neutres sont déjà évalués par le Stand-Pat.
2. **Filtrage exclusif sur les captures déterministes** :
   - Frappes d'anéantissement déterministe à ≥ 1.5× sur une armée adverse.
   - Conversions immédiates sans perte d'humains (Effectif_allié ≥ Humains).
3. **Facteur de branchement maîtrisé** : Le nombre de coups explorés tombe de 30+ à seulement 0, 1 ou 2 coups, permettant de résoudre instantanément l'effet d'horizon tout en préservant le débit de calcul (21 000+ nœuds/sec).

---

## 🧠 6. Le Cœur Décisionnel : Alpha-Bêta, Zobrist & Gestion du Temps

### 6.1. Hachage de Zobrist 64 bits & Table de Transposition

Pour éviter de recalculer des positions identiques atteintes par des ordres de coups différents :
* Chaque case (x, y) possède trois nombres aléatoires 64 bits fixes : `Cle_Humain(x, y)`, `Cle_Vampire(x, y)`, `Cle_Loup(x, y)`.
* La clé de hachage de l'échiquier se met à jour instantanément grâce à l'opération binaire **XOR** :

```text
Hash(Plateau) = Hash_initial XOR [ Somme XOR sur chaque case occupée ]
```

* **Pourquoi le XOR ?**  
  L'opération XOR a la propriété remarquable d'être son propre inverse : `(A XOR B) XOR B = A`.  
  Déplacer une unité d'une case A vers une case B se fait en seulement deux opérations : retirer l'unité de A (`Hash XOR Cle_A`) et l'ajouter en B (`Hash XOR Cle_B`), en **0.0001 milliseconde**.
* Chaque entrée en cache enregistre :
  `TranspositionEntry(depth, score, flag, best_move)` avec drapeaux Exact (0), Borne Inférieure / Cutoff Beta (1), et Borne Supérieure / Échec Alpha (2).

### 6.2. Approfondissement Itératif (Iterative Deepening Search - IDS)
Au lieu de viser une profondeur fixe au risque de dépasser le temps limite de 2.0s, Apex approfondit progressivement :

```text
Profondeur 1  ───>  Profondeur 2  ───>  Profondeur 3  ───>  Profondeur 4  ───>  Profondeur 5 ...
```

* **Budget de sécurité strict :** 1.65 seconde. Si le chronomètre dépasse 1.65 s, la recherche s'interrompt proprement et renvoie le meilleur coup de la profondeur précédente.
* **TT-Move (Coup optimal de la Table de Transposition) :** Le meilleur coup trouvé à la profondeur k - 1 est systématiquement testé en **premier** à la profondeur k. Cela déclenche des coupures Alpha-Bêta immédiates et divise le temps de calcul par 5.

### 6.3. Optimisation Mémoire : Contrôle du Garbage Collector
En Python, les déclenchements imprévus du ramasse-miettes (*Garbage Collector*) peuvent introduire des latences de 50 à 150 ms en pleine recherche.  
Apex encadre l'approfondissement itératif par :
```python
gc_was_enabled = gc.isenabled()
if gc_was_enabled:
    gc.disable()
try:
    # Recherche Minimax Alpha-Bêta
finally:
    if gc_was_enabled:
        gc.enable()
```

---

## 📈 7. Fonction d'Évaluation Heuristique Globale

Pour les positions non terminales, le score statique agrège 6 dimensions stratégiques :

```text
Score_Total = Delta_Materiel + Bonus_Domination + Score_OFR + Danger_Tactique + Traque_Ennemi + Cohesion_Armee
```

| Terme | Rôle Stratégique | Formule de Calcul |
| :--- | :--- | :--- |
| **1. Delta_Materiel** | Différentiel d'armée | `(Effectif_nous - Effectif_ennemi) × 2000` |
| **2. Bonus_Domination** | Seuil de domination 1.5× | `+60 000 + (Effectif_nous - 1.5 × Effectif_ennemi) × 1000` si Effectif_nous ≥ 1.5 × Effectif_ennemi<br>`-60 000 - (Effectif_ennemi - 1.5 × Effectif_nous) × 1000` si Effectif_ennemi ≥ 1.5 × Effectif_nous |
| **3. Score_OFR** | Attraction humaine | Score d'attraction du meilleur village atteignable pondéré par Voronoï |
| **4. Danger_Tactique** | Matrice tactique de contact | `±120 000` si contact à distance d = 1 selon le rapport de force<br>`±25 000` si embuscade possible à distance d = 2 |
| **5. Traque_Ennemi** | Chasse du roi adverse | Si nous dominons (Effectif_nous ≥ 1.5 × Effectif_ennemi) : `- Distance(nous, ennemi) × 400`<br>*(Pousse notre armée à foncer sur l'ennemi pour l'achever)* |
| **6. Cohesion_Armee** | Pénalité de scission | Malus massif si nos troupes sont éparpillées en plusieurs sous-groupes |

---

## 📊 8. Résultats Expérimentaux & Évolution des Performances

### Benchmark Comparatif contre les Rivaux de Référence (Aller-Retour sur 4 Cartes) :

| Adversaire Testé | Type de Jeu | Apex v1 (Base) | Apex v2 (Amélioré) | Progression |
| :--- | :--- | :---: | :---: | :---: |
| [`GreedyReflexAI`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/rival_agents.py#L52) | Glouton ultra-rapide | 62.5% | **75.0%** | **+12.5%** |
| [`TacticalSplitterAI`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/rival_agents.py#L106) | Récolte parallèle scindée | 75.0% | **87.5%** | **+12.5%** |
| [`ShallowMinimaxAI`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/rival_agents.py#L254) | Minimax profondeur 2 | 75.0% | **87.5%** | **+12.5%** |
| [`MonteCarloAI`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/rival_agents.py#L318) | Rollouts aléatoires | 75.0% | **87.5%** | **+12.5%** |

### Le Duel Direct Interne :
Dans un face-à-face rigoureux sur 8 matchs Aller-Retour :
* **Victoires Apex v2 :** **4**
* **Victoires Apex v1 :** **2**
* **Matchs Nuls :** **2**
* **Taux de supériorité net :** **66.7%** de victoires hors nuls.

---

## 🛠️ 9. Guide d'Exécution & Les 3 Agents Disponibles

Le dépôt fournit trois fichiers d'agents autonomes correspondant aux 3 meilleures configurations du championnat :

1. **[`ai_agent_vor_qs.py`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/ai_agent_vor_qs.py) (Champion #1 – Configuration par défaut de `ai_agent.py`) :**  
   *Voronoï + Quiescence Search.* Taux de victoire de **84.4%** contre les rivaux et **66.1%** au tournoi Round-Robin.
2. **[`ai_agent_v2_all.py`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/ai_agent_v2_all.py) (Vice-Champion #2) :**  
   *Version Complète Intégrale (OFR + Voronoï + Quiescence Search).* 62.5% au championnat.
3. **[`ai_agent_ofr_qs.py`](file:///c:/Users/E%20N%20V%20Y/OneDrive%20-%20Ecole%20Centrale%20Casablanca/Bureau/FIA/ai_agent_ofr_qs.py) (Top Dueliste #3) :**  
   *Optimal Foraging Rate + Quiescence Search.* Vitesse de conversion humaine ultra-rapide.

### Commandes de Lancement :
* **Connexion en Match Tournoi Officiel :**
  ```bash
  python connect.py 127.0.0.1 5555
  ```
* **Lancement du Tournoi de Benchmark Complet :**
  ```bash
  python apex_ablation_arena.py
  ```
* **Duel Visuel Instantané contre un Rival :**
  ```bash
  python play_duel.py --rival TacticalSplitterAI --map carree
  ```

---
*Document certifié conforme aux spécifications du projet FIA – CentraleSupélec.*
