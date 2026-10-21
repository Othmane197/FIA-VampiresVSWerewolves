# 🐺 Architecture & Fonctionnement Intégral du Moteur Apex v2 (Guide Technique)
**Projet** : Vampires VS Werewolves (FIA – CentraleSupélec)  
**Auteur** : Équipe Apex (Othmane MAAMAR)  
**Document de Référence** : Rapport d'architecture, modélisation mathématique et soutenance technique

---

## 🏛️ 1. Vue d'Ensemble & Philosophie du Moteur

Le projet *Vampires VS Werewolves* pose un défi combinatoire et stochastique à contrainte temps-réel stricte (**$T \le 2.00\text{ s}$ par coup** via socket TCP). 

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

Dans *Vampires VS Werewolves*, les unités se déplacent sur une grille 2D dans les 8 directions (distance de Chebyshev $d_\infty(A, B) = \max(|x_A - x_B|, |y_A - y_B|)$).  
Chaque déplacement sur une case occupée déclenche une résolution immédiate.

### 2.1. Capture des Humains Neutres
Soit $E_1$ le nombre de monstres attaquants arrivant sur une case contenant $H$ humains :
* **Si $E_1 \ge H$ (Capture Déterministe) :**
  $$\text{Pertes} = 0, \quad E_{\text{final}} = E_1 + H$$
  Tous les humains sont convertis sans aucune perte. L'armée s'accroît instantanément de $H$.
* **Si $E_1 < H$ (Combat Aléatoire Défavorable) :**
  $$P(\text{Victoire}) = \frac{E_1}{2 \times H}$$
  Le taux d'attrition est massif. Même en cas de victoire, l'espérance de survivants est dérisoire.  
  *Conséquence algorithmique :* L'IA s'interdit d'attaquer des humains en sous-effectif.

### 2.2. Combat entre Espèces Rivales (Vampires vs Loups-Garous)
Soit $E_1$ le nombre d'attaquants et $E_2$ le nombre de défenseurs :

```text
        ZONE 1 :                     ZONE 3 :                     ZONE 2 :
    Défaite Certaine             Combat Aléatoire             Victoire Certaine
   (Attaquants anéantis)       (Résolution probabiliste)     (Défenseurs anéantis)
 <-----------------------]-----------------------------------[----------------------->
 0                   E2 / 1.5                             1.5 * E2                  E1
```

* **Zone 2 : Victoire Déterministe ($E_1 \ge 1.5 \times E_2$) :**  
  Victoire absolue à pertes nulles. Les $E_2$ ennemis sont anéantis, nos $E_1$ monstres survivent intégralement.
* **Zone 1 : Défaite Déterministe ($E_2 \ge 1.5 \times E_1$, soit $E_1 \le E_2 / 1.5$) :**  
  Annihilation totale de nos attaquants. L'ennemi conserve ses $E_2$ unités intactes.
* **Zone 3 : Combat Stochastique ($\frac{E_2}{1.5} < E_1 < 1.5 \times E_2$) :**  
  La probabilité de victoire est affine par morceaux :
  $$P = \begin{cases} 
  0.5 & \text{si } E_1 = E_2 \\
  \dfrac{E_1}{2 \times E_2} & \text{si } E_1 < E_2 \\
  \dfrac{E_1}{E_2} - 0.5 & \text{si } E_1 > E_2 
  \end{cases}$$
  En cas de victoire, chaque survivant subit un tirage binomial de probabilité $P$. Pour un combat à effectifs égaux ($10$ contre $10$), l'espérance de survivants est :
  $$\mathbb{E}[\text{Survivants}] = P \times (P \times E_1) = 0.5 \times 0.5 \times 10 = \mathbf{2.5 \text{ unités}}$$
  avec **50% de probabilité de défaite immédiate de la partie**.

> [!IMPORTANT]
> **Le Principe de Concentration de Lanchester ("Deathball") :**  
> En raison du seuil $1.5\times$, regrouper nos troupes en un unique bloc compact crée une supériorité opérationnelle déterminante : aucune troupe adverse dispersée ne peut nous attaquer sans défaite déterministe.

---

## 🗺️ 3. Composant Macro : Le Voronoï Capacitaire (*Capacity-Aware Voronoi*)

### 3.1. Le Problème du "Défenseur Fantôme" (*Ghost Defender*)
Dans les implémentations naïves de Voronoï sur grille, un village $H$ est abandonné dès que l'ennemi le plus proche est métriquement plus près que nous ($d_{\text{ennemi}} < d_{\text{nous}}$).  
*L'erreur fatale :* Si 2 loups sont à distance 2 d'un village de 8 humains, et que nos 15 vampires sont à distance 3, le Voronoï standard abandonnait ce village ! Pourtant, les 2 loups ne peuvent **pas** capturer 8 humains sans un risque de suicide quasi certain ($P \le 12.5\%$).

### 3.2. Modélisation Mathématique
Pour chaque groupe ennemi $e = (\text{pos}_e, E_e)$ et chaque colonie humaine $H = (\text{pos}_H, N_H)$, nous définissons le **Coefficient de Crédibilité de Menace** $C(e, H) \in [0, 1]$ :

$$C(e, H) = \begin{cases} 
1.0 & \text{si } E_e \ge N_H \quad \text{(Capacité de capture déterministe)} \\
\max\left(0.05, \dfrac{E_e}{2 \times N_H}\right) & \text{si } E_e < N_H \quad \text{(Menace probabiliste faible)}
\end{cases}$$

La **Distance Effective Adverse** $d_{\text{eff}}(e, H)$ s'écrit alors :
$$d_{\text{eff}}(e, H) = \frac{d_\infty(e, H)}{C(e, H)}$$

```text
EXEMPLE DU DÉFENSEUR FANTÔME RÉSOLU :
Village : 8 humains. Ennemi : 2 loups à d = 2. Notre armée : 15 vampires à d = 3.

• Calcul naïve v1 :  d_ene = 2 < d_nous = 3  ───> Cible abandonnée ❌ (Gaffe !)
• Voronoï Capacitaire :
  C(e, H) = 2 / (2 × 8) = 0.125
  d_eff = 2 / 0.125 = 16 cases !
  d_nous = 3 << 16  ───> Cible dans notre Voronoï exclusif garanti ✅ (Ratio 1.4)
```

### 3.3. Les Trois Régimes Territoriaux
$$\text{Ratio}(H) = \begin{cases} 
0.0 & \text{si } \min_e d_{\text{eff}}(e, H) < d_\infty(\text{nous}, H) \quad \text{(Cellule ennemie crédible : abandon)} \\
1.4 & \text{si } d_\infty(\text{nous}, H) < \min_e d_{\text{eff}}(e, H) \quad \text{(Cellule alliée garantie : priorité haute)} \\
1.0 & \text{si égalité} \quad \text{(Frontière contestée)}
\end{cases}$$

---

## 🍎 4. Composant Méso : Théorie du Butinage Optimal (*Optimal Foraging Rate - OFR*)

### 4.1. Le Rendement Marginal Temporel
Dans les versions antérieures, l'attraction d'une colonie humaine était formulée avec un exposant supra-linéaire sur l'effectif : $\frac{N_{\text{hum}}^{1.1}}{d + 1}$.  
Cela créait le piège des "longs pèlerinages" : l'IA délaissait un groupe de 2 humains adjacent ($d=1$) pour courir pendant 6 tours vers un groupe de 8 humains, laissant le tempo à l'adversaire.

Inspirée par la *Théorie du Butinage Optimal* (Charnov), la formule v2 calcule le gain net par unité de temps dépensée :

$$\text{Pull}_{\text{OFR}}(H) = \frac{W_{\text{pull}} \cdot N_{\text{hum}} \cdot \text{Ratio}_{\text{voronoi}}}{(d + 0.5)^{1.6}} + \mathbb{I}(d = 1) \cdot 8000$$

### 4.2. Caractéristiques Clés :
1. **Linéarité de la ressource ($N_{\text{hum}}$)** : Pas de distorsion artificielle en faveur des cibles géantes.
2. **Décroissance supra-linéaire de la distance ($(d + 0.5)^{1.6}$)** : Amortit très rapidement les gains espérés au-delà de 3 tours.
3. **Prime absolue d'absorption immédiate ($+8000\text{ pts}$ à $d=1$)** : Absorber un groupe en 1 coup augmente nos effectifs dès le tour suivant et décale instantanément le seuil de domination $1.5\times$ à notre avantage.

---

## 🛡️ 5. Composant Micro : Quiescence Search (Recherche de Repos Tactique)

### 5.1. Résolution de l'Effet d'Horizon
À profondeur $depth = 0$, un Minimax standard évalue statiquement la position. Si deux armées se trouvent au contact immédiat ($d=1$), l'évaluation statique voit notre armée intacte et renvoie un score favorable, ignorant le massacre au tour suivant.

### 5.2. Principe du Stand-Pat & Détection d'Instabilité
À la feuille, l'algorithme teste s'il y a un contact direct avec l'ennemi :
$$\text{Contact Tactique} \iff \exists (\text{allié}, \text{ennemi}) \text{ tel que } d_\infty(\text{allié}, \text{ennemi}) = 1$$
* Si aucun contact : la position est **quiescente** (stable), on renvoie immédiatement `Evaluate(state)`.
* Si contact présent : la recherche s'étend récursivement sur un pli tactique additionnel ($qdepth = 1$).

```python
def quiescence_search(self, state, alpha, beta, maximizing_player, root_species, qdepth=1):
    stand_pat = self.evaluate(state, root_species)
    if qdepth <= 0 or not has_contact:
        return stand_pat
```

### 5.3. Correction Critique : Le Piège du "Stand-Pat sous Menace" (*In-Check Trap*)
Dans les implémentations classiques d'échecs, un joueur ne peut pas faire "Stand-Pat" lorsqu'il est en échec.  
Dans *Vampires VS Werewolves*, si notre armée est adjacente à une force ennemie ayant une supériorité $\ge 1.5\times$, nous sommes **en prise mortelle**.
* **Notre correction :** Si l'armée est sous menace létale directe ($E_{\text{ennemi}} \ge 1.5 \times E_{\text{nous}}$ à $d=1$), **le Stand-Pat est désactivé** : le joueur MAX n'a pas le droit de considérer la position statique comme acceptable et est forcé de chercher un coup d'évasion ou de riposte.

### 5.4. Ordonnancement Heuristique dans la Quiescence
Pour déclencher des coupures $\beta$ quasi-instantanées sans explorer les 8 directions neutres, les coups en Quiescence sont strictement priorisés :
1. **Frappes létales $1.5\times$** : $+50\,000\text{ pts}$ (destruction garantie de l'ennemi).
2. **Conversions immédiates d'humains à $d=1$** : $+15\,000\text{ pts} + H \times 100$.
3. **Évasions hors de portée létale** : $+10\,000\text{ pts}$.
4. **Pénalisation absolue des suicides** : $-100\,000\text{ pts}$.

---

## 🧠 6. Le Cœur Décisionnel : Alpha-Bêta, Zobrist & Gestion du Temps

### 6.1. Hachage de Zobrist 64 bits & Table de Transposition
Pour éliminer l'exploration redondante des transpositions (ex: ordre commuté de déplacements menant au même plateau) :
* À chaque case $(x, y)$ et chaque entité (Humain, Vampire, Loup-Garou) est assignée une clé pseudo-aléatoire 64-bit fixe (`random.getrandbits(64)` initialisé avec graine 42).
* Le hash de l'état se calcule par opérations bit-à-bit XOR ($\oplus$) :
  $$H(\text{State}) = H_{\text{init}} \oplus \bigoplus_{(x, y)} (K_{\text{hum}}(x, y) \cdot H + K_{\text{vmp}}(x, y) \cdot V + K_{\text{wrw}}(x, y) \cdot W)$$
* Chaque entrée en cache enregistre :
  `TranspositionEntry(depth, score, flag, best_move)` avec drapeaux Exact ($0$), Borne Inférieure / Cutoff $\beta$ ($1$), et Borne Supérieure / Échec $\alpha$ ($2$).

### 6.2. Approfondissement Itératif (Iterative Deepening Search - IDS)
Au lieu de viser une profondeur fixe qui risquerait de dépasser le budget de 2.0s, Apex utilise une boucle d'approfondissement progressif :
$$\text{Profondeur } 1 \longrightarrow 2 \longrightarrow 3 \longrightarrow 4 \longrightarrow 5 \longrightarrow 6$$
* **Budget de sécurité strict :** $1.65\text{ seconde}$. Si $t > 1.65\text{ s}$, le calcul s'interrompt immédiatement et renvoie le meilleur coup consolidé de la profondeur précédente.
* **Réutilisation du coup optimal de la table de transposition (TT-Move) :** Le meilleur coup trouvé à la profondeur $k-1$ est systématiquement exploré en **première position** à la profondeur $k$, assurant un taux maximal de coupures $\alpha-\beta$ (proche de la borne théorique $O(b^{d/2})$).

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

Pour les positions non terminales, le score statique agrège 5 dimensions stratégiques :

$$\text{Score}(S) = \Delta_{\text{mat}} + \Phi_{\text{dom}} + \Phi_{\text{foraging}} + \Psi_{\text{danger}} + \Omega_{\text{pursuit}} + \Gamma_{\text{cohesion}}$$

1. **Différentiel Matériel ($\Delta_{\text{mat}}$) :**
   $$(E_{\text{nous}} - E_{\text{ennemi}}) \times W_{\text{material}} \quad (W = 2000)$$
2. **Seuil de Domination Non-Linéaire ($\Phi_{\text{dom}}$) :**
   $$\begin{cases} 
   +60\,000 + (E_{\text{nous}} - 1.5 E_{\text{ennemi}}) \times 1000 & \text{si } E_{\text{nous}} \ge 1.5 E_{\text{ennemi}} \\
   -60\,000 - (E_{\text{ennemi}} - 1.5 E_{\text{nous}}) \times 1000 & \text{si } E_{\text{ennemi}} \ge 1.5 E_{\text{nous}}
   \end{cases}$$
3. **Gradient d'Attraction Humaine ($\Phi_{\text{foraging}}$) :**
   Attraction calculée par l'OFR pondéré par le Voronoï capacitaire vers le village optimal.
4. **Matrice de Menace & Danger ($\Psi_{\text{danger}}$) :**
   * À distance 1 : $+120\,000$ si coup d'annihilation $1.5\times$ possible ; $-150\,000$ si embuscade subie ; $-50\,000$ si combat à 50% de tirage de dés.
   * À distance 2 : $-25\,000$ si l'adversaire peut bondir avec supériorité ; $+15\,000$ si nous préparons l'embuscade.
5. **Mode Traque Absolue / Chasse au Roi ($\Omega_{\text{pursuit}}$) :**
   Dès que le seuil de domination $1.5\times$ est franchi ou que tous les humains sont absorbés :
   $$\Omega_{\text{pursuit}} = - \min_{(g, e)} d_\infty(g, e) \times 400$$
   L'armée traque agressivement l'ennemi pour forcer le contact et clore la partie.

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
