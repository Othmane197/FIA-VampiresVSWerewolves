# Guide Technique : Algorithme Minimax Alpha-Bêta (Apex)
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

#### Choix Stratégique : La Préservation du Bloc Unique
La règle permet de scinder une armée en plusieurs groupes. **Faut-il le faire ?**
* Si vous avez $10$ monstres et vous divisez en $5$ et $5$ :
  * L'ennemi (qui a $10$) n'a besoin que de $1.5 \times 5 = 7.5 \implies 8$ monstres pour détruire votre premier groupe sans aucune perte.
  * Il vous élimine par morceaux.
* En restant groupé à $10$, l'ennemi doit atteindre $15$ monstres pour vous attaquer en toute sécurité.
* L'algorithme privilégie donc systématiquement le maintien d'une armée unie.

```python
# Maintien de l'armée sous forme d'un bloc unifié
if len(groups) == 1:
    (src_x, src_y), count = groups[0]
    src = (src_x, src_y)
    neighbors = state.get_neighbors(src)
    valid_destinations = [n for n in neighbors if n not in sources] or neighbors

    for dst in valid_destinations:
        candidate_list.append([(src_x, src_y, count, dst[0], dst[1])])
    return candidate_list
```

---

### Composant 3 : Gestion du Temps (Approfondissement Itératif)
*Fichier* : [`apex_agent.py`](apex_agent.py) (`compute_moves`)

Le protocole impose une limite stricte de **2,0 secondes par coup**. Dépasser ce temps entraîne la perte du tour.

**Problème** : Le facteur de branchement variant selon la partie, lancer directement une recherche à profondeur 4 ou 5 risque d'exploser le budget temps si l'arbre est trop large.

**Solution : L'Approfondissement Itératif (Iterative Deepening Search - IDS)** :
1. Calculer la meilleure réponse à **Profondeur 1** ($\sim 1 \text{ ms}$). Sauvegarder ce coup.
2. S'il reste du temps, calculer à **Profondeur 2** ($\sim 10 \text{ ms}$). Mettre à jour.
3. Continuer avec **Profondeur 3**, **Profondeur 4**...
4. Un chronomètre vérifie en continu : dès que $t \ge 1.65 \text{ s}$, la recherche s'interrompt immédiatement.
5. L'algorithme renvoie le meilleur coup issu de la dernière profondeur entièrement explorée.

```python
# Recherche à profondeur croissante avec garde-fou temporel
for depth in range(1, 7):
    if time.time() - self.start_time > 1.65:
        break  # Seuil de sécurité atteint : on évite le timeout

    for move in candidate_moves:
        child_state = state.apply_moves(move, species, deterministic=True)
        score = self.alpha_beta(child_state, depth - 1, alpha, beta, False, species)
        ...
```

---

### Composant 4 : Ordonnancement des Coups et Élagage Alpha-Bêta

L'efficacité de l'élagage Alpha-Bêta dépend directement de l'ordre dans lequel les coups sont examinés :
* **Cas défavorable** (coups examinés du pire au meilleur) : complexité en $O(b^d)$.
* **Cas optimal** (meilleur coup examiné en premier) : complexité réduite à $O(b^{d/2})$, doublant virtuellement la profondeur accessible pour le même temps de calcul.

L'algorithme trie les branches selon des priorités tactiques :
1. Le coup recommandé par la **Table de Transposition** au tour précédent.
2. Les attaques assurant une destruction certaine à $1.5\times$ de l'ennemi.
3. Les captures d'humains sans risque ($E_{\text{notre}} \ge E_{\text{humains}}$).
4. Évitement des cases sous la menace directe d'un adversaire supérieur à $1.5\times$.

---

### Composant 5 : Fonction d'Évaluation Heuristique (`evaluate`)
*Fichier* : [`apex_agent.py`](apex_agent.py)

À la profondeur maximale de l'arbre, on évalue la qualité de la position selon cinq critères pondérés :

1. **Différentiel de Troupes (Matériel)** :
   $$\text{Score}_{\text{mat}} = (N_{\text{alliés}} - N_{\text{ennemis}}) \times 2000$$

2. **Seuil de Domination ($1.5\times$)** :
   Dès que notre effectif total dépasse $1.5 \times N_{\text{ennemis}}$, la partie est mathématiquement gagnante. On injecte un bonus majeur de $+60\,000$ points.

3. **Gradient d'Attraction vers les Humains** :
   Pour chaque colonie humaine convertible sans pertes, on calcule un potentiel attractif inversement proportionnel à la distance de Chebyshev $d$ :
   $$\text{Attraction} = \frac{3000 \times N_{\text{humains}}}{d + 1}$$
   Ce gradient continu guide l'armée vers les cibles prioritaires sans hésitation ni mouvement oscillant.

4. **Matrice Anti-Embuscade** :
   Si une case d'arrivée place notre armée à distance $1$ d'un groupe ennemi capable de nous éliminer au tour suivant ($E_{\text{ennemi}} \ge 1.5 \times E_{\text{nous}}$), une pénalité critique de $-150\,000$ points est appliquée.

5. **Traque Finale (Endgame)** :
   Lorsque tous les humains sont convertis ou que notre supériorité est acquise, l'heuristique minimise la distance à l'ennemi pour forcer le contact et clore la partie.

---

## 4. Guide d'Exécution et de Test

| Commande | Rôle |
| :--- | :--- |
| `python tournament_arena.py` | Lance un tournoi local automatisé testant l'algorithme contre 5 IA rivales (Aléatoire, Réflexe Glouton, Champs de Potentiels, Minimax Simple, Monte Carlo) avec alternance des camps (Vampires et Loups-Garous). |
| `python play_duel.py --rival PotentialFieldAI` | Démarre le serveur graphique officiel (`VampiresVSWerewolvesGameServer.exe`) et affiche le match en direct sur l'interface WPF. |
| `python main.py <IP> <PORT>` | Mode officiel de compétition : connecte le bot au serveur de tournoi du professeur. |
