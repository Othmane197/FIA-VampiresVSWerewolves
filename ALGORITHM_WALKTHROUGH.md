# Guide Technique : Algorithme Minimax Alpha-Bêta (Apex V3.1 Flagship)
**Projet** : Vampires VS Werewolves (FIA – CentraleSupélec)  
**Profil cible** : Ingénieur Généraliste (Notions d'algorithmique, d'arbres et de probabilités)

---

## 1. Modélisation Mathématique des Combats

Lorsqu'un groupe de monstres se déplace sur une case occupée, un combat est résolu instantanément.  
Soit :
* $E_1$ : nombre de monstres attaquants (ceux qui arrivent sur la case).
* $E_2$ : nombre de monstres défenseurs (ceux déjà présents sur la case).

### Diagramme des Régimes de Combat

```text
       ZONE 1 :                     ZONE 3 :                     ZONE 2 :
   Défaite Certaine             Combat Aléatoire             Victoire Certaine
  (Attaquants anéantis)       (Résolution probabiliste)     (Défenseurs anéantis)
<-----------------------]-----------------------------------[----------------------->
0                   E2 / 1.5                             1.5 * E2                  E1
```

---

### Analyse des 3 Régimes

#### Régime 1 : Victoire Déterministe ($E_1 \ge 1.5 \times E_2$)
* **Condition** : Les attaquants ont une supériorité numérique d'au moins **50%**.
* **Résultat** : Victoire garantie sans aucune perte.
  * Tous les $E_2$ défenseurs sont éliminés.
  * Tous les $E_1$ attaquants survivent (pertes $= 0$).
* *Exemple numérique* : $15$ Vampires attaquent $10$ Loups-Garous.  
  $15 \ge 1.5 \times 10 = 15 \implies$ Les 10 Loups-Garous meurent, vos 15 Vampires restent intacts.

#### Régime 2 : Défaite Déterministe ($E_2 \ge 1.5 \times E_1$, soit $E_1 \le E_2 / 1.5$)
* **Condition** : Le défenseur a une supériorité d'au moins **50%**.
* **Résultat** : Défaite totale de l'attaquant sans pertes pour le défenseur.
  * Tous les $E_1$ attaquants sont éliminés.
  * Le défenseur conserve tous ses $E_2$ monstres intacts.
* *Exemple numérique* : $6$ Vampires attaquent $10$ Loups-Garous.  
  $10 \ge 1.5 \times 6 = 9 \implies$ Les 6 Vampires meurent, les 10 Loups-Garous restent intacts.

#### Régime 3 : Combat Probabiliste (Quand aucun camp n'a le ratio $1.5\times$)
Dans l'intervalle intermédiaire $\frac{E_2}{1.5} < E_1 < 1.5 \times E_2$, l'issue est aléatoire.  
La probabilité $P$ que l'attaquant gagne est une **fonction affine par morceaux** reliant les points $(0, 0)$, $(E_2, 0.5)$ et $(1.5 E_2, 1.0)$ :

$$P = \begin{cases} 
0.5 & \text{si } E_1 = E_2 \\
\dfrac{E_1}{2 \times E_2} & \text{si } E_1 < E_2 \\
\dfrac{E_1}{E_2} - 0.5 & \text{si } E_1 > E_2 
\end{cases}$$

#### Survie et Pertes en Combat Aléatoire :
Même en cas de victoire, le vainqueur subit des pertes :
* **Si l'attaquant gagne** (probabilité $P$) : chaque monstre attaquant a individuellement une probabilité $P$ de survivre.
* **Si l'attaquant perd** (probabilité $1 - P$) : chaque monstre défenseur a individuellement une probabilité $1 - P$ de survivre.

#### Conséquence Algorithmique (Espérance Mathématique) :
Pour un combat équilibré ($10$ contre $10$) :
$$\mathbb{E}[\text{survivants attaquants}] = P \times (P \times E_1) = 0.5 \times 0.5 \times 10 = 2.5 \text{ unités}$$
Avec un **risque de 50% de défaite immédiate de la partie**.  
**Décision d'ingénierie** : L'algorithme pénalise fortement les combats aléatoires. Il privilégie la conversion des humains pour franchir mathématiquement le seuil des $1.5\times$, garantissant des victoires à pertes nulles.

---

## 2. Architecture Globale du Système

```text
                           +------------------------+
                           |  Serveur de Jeu (TCP)  |
                           +-----------+------------+
                                       | Message UPD (état du tour)
                                       v
                           +------------------------+
                           |  Convertisseur d'État  |
                           +-----------+------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                      Moteur de Décision (ApexAlphaBeta)                       |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | Approfondissement Itératif (Iterative Deepening)                        |  |
|  | Boucle : Profondeur 1 -> 2 -> 3 -> 4...                                 |  |
|  | Gestion du budget temps : Arrêt strict si t > 1.65 secondes             |  |
|  +------------------------------------+------------------------------------+  |
|                                       |                                       |
|        +------------------------------+-------------------------------+       |
|        v                                                              v       |
|  +---------------------------+                          +-------------------+ |
|  | Générateur de Mouvements  |                          | Table de          | |
|  | - Respect Règles 1 à 6    |                          | Transposition     | |
|  | - Maintien du bloc unique |                          | - Hachage Zobrist | |
|  | - Tri heuristique des coups|                         | - Cache 64 bits   | |
|  +-------------+-------------+                          +---------+---------+ |
|                |                                                  |           |
|                v                                                  |           |
|  +----------------------------------------------------------------+--------+  |
|  |                        Cœur Minimax Alpha-Bêta                          |  |
|  |  - (how)Élagage Alpha-Bêta (Coupes rapides des branches sous-optimales)      |  |
|  |  - (how)Réutilisation des bornes déjà calculées (Exact, Sup, Inf)            |  |
|  +------------------------------------+------------------------------------+  |
|                                       |                                       |
|                                       v                                       |
|  +-------------------------------------------------------------------------+  |
|  | Fonction d'Évaluation Heuristique (État des feuilles de l'arbre)        |  |
|  |  1. Différentiel de troupes (+2000 * delta)                             |  |
|  |  2. Seuil de domination (+60 000 si total >= 1.5 * ennemi)              |  |
|  |  3. Gradient d'attraction vers les humains sécurisés                    |  |
|  |  4. Matrice de danger (-150 000 si position d'embuscade ennemie)        |  |
|  |  5. Mode traque / Fin de partie (minimisation de la distance Chebyshev)|  |
|  +-------------------------------------------------------------------------+  |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
                           +------------------------+
                           |  Trame MOV (Socket TCP)|
                           +------------------------+
```

---

## 3. Détail des Composants Clés

### Composant 1 : Représentation d'État et Hachage Zobrist
*Fichier* : [`apex_agent.py`](apex_agent.py)

Dans un jeu à deux joueurs, plusieurs séquences de mouvements distinctes mènent à la même configuration spatiale :
$$\text{Coup } A \text{ puis Coup } B \equiv \text{Coup } B \text{ puis Coup } A$$

Pour éviter d'explorer deux fois le même sous-arbre, on utilise une **table de transposition** indexée par une clé de hachage de 64 bits :
* À chaque case $(x, y)$ et chaque type d'entité (Humain, Vampire, Loup-Garou) est associé un entier aléatoire 64 bits.
* La clé d'un plateau est calculée par un ensemble d'opérations bit-à-bit `XOR` ($\oplus$).
* Le coût de mise à jour d'un plateau est en $O(k)$ où $k$ est le nombre de cases actives, rendant la consultation du cache quasi-instantanée ($O(1)$).

```python
class TranspositionEntry:
    __slots__ = ('depth', 'score', 'flag', 'best_move')
    def __init__(self, depth: int, score: float, flag: int, best_move: list):
        self.depth = depth          # Profondeur à laquelle le nœud a été calculé
        self.score = score          # Valeur minimax du nœud
        self.flag = flag            # 0 = Valeur exacte, 1 = Borne inférieure, 2 = Borne supérieure
        self.best_move = best_move  # Meilleur coup trouvé à cette profondeur
```

---

### Composant 2 : Génération des Coups et Stratégie de Bloc
*Fichier* : [`apex_agent.py`](apex_agent.py) (`generate_moves`)

Le générateur applique strictement les contraintes imposées par le cahier des charges :
1. **Règles 1 et 6** : Au moins un déplacement d'au moins 1 créature par tour.
2. **Règles 2 et 3** : Déplacement réservé à notre espèce ; contrôle des effectifs sources.
3. **Règle 4** : 8 directions adjacentes (distance de Chebyshev $= 1$).
4. **Règle 5** : Une case ne peut pas être à la fois source et destination au même tour.

#### Évolution Stratégique V3.1 : Le Multi-Splitting Dynamique et Sécurisé
Bien que la préservation du bloc unifié protège contre les embuscades, elle bride l'expansion économique sur les cartes étendues contenant de multiples villages. **Apex V3.1 Flagship** introduit le **Multi-Splitting Dynamique** :

1. **Vérification Lanchester Stricte (`_split_is_safe`)** :
   - Un détachement de taille $k$ vers un village de $h$ humains ($k \ge h$) n'est autorisé que si aucun ennemi ne peut l'intercepter en cours de route ($\text{dist} \le t$) ni l'anéantir à son arrivée ($E_{\text{ennemi}} < 1.5 (k + h)$).
2. **Expansion Parallèle ($N \le 6$ Groupes)** :
   - Le plafond de groupes actifs s'adapte dynamiquement à la taille de la carte ($N \le 3$ sur petite carte, $N \le 5$ sur moyenne carte, $N \le 6$ sur carte géante).
   - Plans `split+go` et `dual_split+go` : le corps principal continue sa course pendant que 1 ou 2 détachements sécurisés récoltent des villages adjacents ou distants en parallèle.
3. **Génération par Faisceau (Beam Generation)** :
   - Pour éviter l'explosion combinatoire $8^k$, le moteur utilise un faisceau de coups conjoints : 1 coup glouton coordonné + des variantes ciblées par groupe (8 à 12 combinaisons testées au total par Minimax).
4. **Fusion Proactive de Coalition (`Coalition Merger`)** :
   - Lorsque les villages sont épuisés ou qu'une menace $\ge 1.5\times$ approche à distance $\le 2$, une gravité cohésive rassemble les groupes avant l'affrontement décisif.

---

### Composant 3 : Gestion du Temps (Approfondissement Itératif)
*Fichier* : [`apex_agent.py`](apex_agent.py) (`compute_moves`)

Le protocole impose une limite stricte de **2,0 secondes par coup**. Dépasser ce temps entraîne la perte du tour.

**Solution : L'Approfondissement Itératif (Iterative Deepening Search - IDS)** :
1. Calculer la meilleure réponse à **Profondeur 1** ($\sim 1 \text{ ms}$). Sauvegarder ce coup.
2. S'il reste du temps, calculer à **Profondeur 2** ($\sim 10 \text{ ms}$). Mettre à jour.
3. Continuer avec **Profondeur 3**, **Profondeur 4**...
4. Un chronomètre vérifie en continu : dès que $t \ge 1.65 \text{ s}$, la recherche s'interrompt immédiatement.
5. L'algorithme renvoie le meilleur coup issu de la dernière profondeur entièrement explorée.

---

### Composant 4 : Ordonnancement des Coups et Élagage Alpha-Bêta

L'efficacité de l'élagage Alpha-Bêta dépend directement de l'ordre dans lequel les coups sont examinés :
* **Cas optimal** (meilleur coup examiné en premier) : complexité réduite à $O(b^{d/2})$, doublant virtuellement la profondeur accessible.

L'algorithme trie les branches selon des priorités tactiques :
1. Le coup recommandé par la **Table de Transposition** au tour précédent.
2. Les attaques assurant une destruction certaine à $1.5\times$ de l'ennemi.
3. Les captures d'humains sans risque ($E_{\text{notre}} \ge E_{\text{humains}}$).
4. Évitement des cases sous la menace directe d'un adversaire supérieur à $1.5\times$.

---

### Composant 5 : Fonction d'Évaluation Heuristique (`evaluate`) & Résolution Probabiliste
*Fichier* : [`apex_agent.py`](apex_agent.py) et [`game_engine.py`](game_engine.py)

À la profondeur maximale de l'arbre, la position est évaluée selon les piliers tactiques et prédictifs :

1. **Résolution à l'Espérance Mathématique Réelle (Combat EV)** :
   Dans [`game_engine.py`](game_engine.py), les combats probabilistes $E_1 < 1.5 E_2$ sont résolus selon la véritable espérance : si $P \ge 0.5$, l'attaquant gagne à l'espérance avec $P \times E_1$ survivants. Cela élimine les attaques suicidaires et les fausses sécurités défensives.

2. **Élimination de l'Illusion d'Horizon de Domination** :
   Le bonus majeur de domination $+60\,000$ points (`W_DOMINATION_BONUS`) est strictement différé à la fin de partie (`not human_groups`). Pendant la phase d'expansion, l'évaluation privilégie la **Projection de Course à 25 Tours (`_project_race`)** avec un bonus amplifié (+35,000 points), empêchant Minimax de préférer un monobloc myope à une scission récolteuse rentable.

3. **Différentiel de Troupes (Matériel Actuel & Projeté)** :
   $$\text{Score}_{\text{mat}} = (N_{\text{alliés}} - N_{\text{ennemis}}) \times 2000 + (\Delta_{\text{projeté, alliés}} - \Delta_{\text{projeté, ennemis}}) \times 1500$$

4. **Matrice de Menace Lanchester & Évitement des Bordures** :
   Pénalité fatale ($-150\,000$ points) si un groupe s'expose à portée $1.5\times$ d'un groupe ennemi adjacent. En cas de repli, l'algorithme applique une répulsion des bords (`min(b_dist, 3) * 120.0`) pour empêcher l'adversaire d'acculer nos unités dans un coin.

---

### Composant 6 : Élagage de Déplacement en Transit (*Transit Move Pruning*)

Lorsque les groupes sont en plein transit ($d_{\text{ennemi}} \ge 4$ et $d_{\text{humain}} > 1$), tous les coups qui augmentent la distance à la cible sont élagués. Le facteur de branchement s'effondre de $b = 8$ à **$b \approx 2$**, permettant d'atteindre une **profondeur de 10 à 14 plys** en milieu de jeu.

---

## 5. Bilan des Performances & Validation Expérimentale V3.1

### 5.1. Tournoi de Validation vs Mohamed Flagship (10 Matchs Aléatoires)
Testé sur 5 formats de cartes dynamiques (Aller et Retour avec alternance des espèces) :

| Carte | Format | Aller | Retour | Bilan |
| :--- | :---: | :---: | :---: | :---: |
| `Petite_7x9` | $7\times 9$ (6u) | **Apex GAGNE (12 - 0)** 🏆 | **Apex GAGNE (3 - 0)** 🏆 | **2 - 0 (Clean Sweep)** |
| `Carree_11x10` | $11\times 10$ (8u) | Mohamed (17 - 29) | Mohamed (0 - 29) | 0 - 2 |
| `Carree_12x11` | $12\times 11$ (8u) | **Apex GAGNE (15 - 6)** 🏆 | Mohamed (21 - 27) | **1 - 1 (Égalité)** |
| `Grande_14x16` | $14\times 16$ (10u) | **Apex GAGNE (28 - 0)** 🏆 | Mohamed (0 - 7) | **1 - 1 (Égalité)** |
| `Geante_18x20` | $18\times 20$ (12u) | Mohamed (0 - 55) | Mohamed (22 - 52) | 0 - 2 |
| **Total** | — | — | — | **Apex 4 – 6 Mohamed** *(Parité 4-4 sur cartes classiques)* |

### 5.2. Batterie Anti-Surapprentissage (18 Matchs vs Rivals Indépendants)
Pour certifier que le modèle ne souffre d'aucun surapprentissage face au Splitter de Mohamed :
* **Vs `GreedyReflexAgent`** : **Apex 3 - 3** (50.0%)
* **Vs `PotentialFieldAgent`** : **Apex 5 - 1** (83.3%)
* **Vs `TacticalSplitterAgent`** : **Apex 5 - 1** (83.3%)
* **Bilan Global Anti-Overfitting** : **13 Victoires – 5 Défaites (72.2% de victoires)**.

---

## 6. Guide d'Exécution et de Test

| Commande | Rôle |
| :--- | :--- |
| `python tournament_arena.py` | Lance un tournoi local automatisé testant l'algorithme contre 5 IA rivales avec alternance des camps. |
| `python play_duel.py --rival PotentialFieldAI` | Démarre le serveur graphique officiel (`VampiresVSWerewolvesGameServer.exe`) et affiche le match en direct sur l'interface WPF. |
| `python main.py <IP> <PORT>` | Mode officiel de compétition : connecte le bot au serveur de tournoi du professeur. |
