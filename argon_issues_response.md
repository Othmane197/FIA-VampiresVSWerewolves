# Compte-Rendu & Diagnostic d'Argon : Résolution des Verrous Techniques d'Apex (FIA)

Document de synthèse suite à la consultation d'**Argon** sur les défaillances expérimentales (régression Quiescence Search, interférence Voronoï/OFR, faille du défenseur fantôme et scission macroscopique).

---

## 1. Diagnostic de la Régression Quiescence Search (QS)

### Pourquoi les scores se sont effondrés :
Dans l'architecture de départ (`Apex_OFR_QS` à **81.2%** de victoires contre les rivaux), la QS n'était qu'une extension d'un seul demi-coup avec coupure `Stand-Pat` systématique. 

Le passage à la désactivation du `Stand-Pat` sous menace létale (`under_lethal_threat`) combiné au tri tactique des coups a provoqué 3 catastrophes :

1. **Destruction des coupures $\beta$ aux feuilles (70% à 85% des nœuds de l'arbre)** :
   En forçant `stand_pat = -inf` dès qu'un groupe allié est à $d = 1$ d'un ennemi $\ge 1.5\times$, on supprime la coupure immédiate `if stand_pat >= beta: return beta` avant même de générer les coups, et on empêche le `stand_pat` de relever la borne `alpha`. Résultat : le moteur est contraint de générer et d'évaluer tous les coups d'évasion sur des milliers de feuilles au lieu de couper en $\mathcal{O}(1)$.
2. **L'effet « Ping-Pong de Chebyshev »** :
   En distance de Chebyshev ($L_\infty$), sur les 8 mouvements possibles autour d'une menace adjacente ($d = 1$), 5 mouvements laissent l'escouade à $d = 1$ et 3 seulement permettent de s'éloigner à $d = 2$. Si la QS réitère, l'ennemi recolle à $d = 1$ au demi-coup suivant : `under_lethal_threat` reste actif en permanence et l'arbre d'évasion explose de manière exponentielle.
3. **Surcoût CPU du tri Python dans les feuilles** :
   Allouer des listes et exécuter un `.sort()` en Python pur à $depth \le 0$ coûte plus cher que d'évaluer directement le premier coup élagueur. Cela ampute sévèrement le budget de **1.65 seconde** et réduit l'Iterative Deepening à une profondeur de 2 ou 3 (perte de vision stratégique globale).

### Le Correctif d'Argon pour la QS :
* **Règle 1 : Restaurer le `Stand-Pat` inconditionnel (100% du temps).** Ne jamais désactiver le `Stand-Pat` en QS. Les fuites face aux menaces relèvent de l'arbre Alpha-Beta principal ($depth \ge 1$). À $depth = 0$, la fonction statique `evaluate(state)` inflige simplement une pénalité de danger au score `Stand-Pat`.
* **Règle 2 : Plafond strict à 1 seul demi-coup ($qdepth = 1$)** et restreint exclusivement aux **Captures Déterministes** ($\ge 1.5\times$ ou conversion humaine directe). Aucun coup d'évasion ni mouvement neutre en QS.
* **Règle 3 : Suppression totale du tri (`.sort()`) en QS.** Évaluer les coups de capture dans leur ordre d'apparition naturel sans allocation superflue.

---

## 2. Résolution du Conflit Voronoï (VOR) vs Foraging (OFR)

### Pourquoi `Apex_v2_All` a chuté à la 5ème place (52.7%) :
- L'**OFR** incite l'agent à foncer sur les colonies humaines proches avec un bonus massif à $d = 1$.
- Le **Voronoï binaire** (`if d_enemy < d_us: pull = 0`) applique un veto brutal : dès qu'un ennemi est virtuellement plus proche d'une seule case, l'attraction chute instantanément à zéro.
- Cette discontinuité abrupte engendre des hésitations oscillatoires (l'agent s'avance, détecte le veto, recule, puis réavance).

### La Solution d'Argon : Voronoï Capacitaire Continu ($\Gamma_{VOR}$)
Remplacer le veto binaire par un **facteur d'atténuation non-linéaire et continu** $\Gamma_{VOR}(h) \in [0, 1.5]$ appliqué au rendement OFR de chaque village $h$ :

$$\Gamma_{VOR}(h) = \sigma\left( k \cdot \left( d_{\text{enemy}}(h) - d_{\text{us}}(h) + \Delta_{\text{capacity}} \right) \right)$$

* **Offset dynamique $\Delta_{\text{capacity}}$** : si notre groupe principal est $\ge 1.5\times$ l'ennemi le plus proche, $\Delta_{\text{capacity}} = +1$ (nous conservons le droit de contester ou d'écraser l'ennemi même s'il a une case d'avance).
* **Bénéfice** : transition douce et naturelle entre avidité territoriale et prudence sans jamais bloquer l'agent.

---

## 3. Faille du « Défenseur Fantôme » sous Effectifs Réduits

### Le problème :
Une petite escouade ennemie (ex: 2 loups devant 8 humains) était considérée comme bloquant l'accès au village car $d_{\text{enemy}} < d_{\text{us}}$, alors que l'ennemi se suiciderait s'il tentait la capture.

### La Solution d'Argon : Coefficient de Crédibilité $C(e, h)$
$$C(e, h) = \min\left(1.0, \frac{\text{Effectif}(e)}{\text{Effectif}_{\text{critique}}(h)}\right)$$
- Si l'effectif ennemi $e$ est inférieur au seuil critique requis pour capturer le village sainement ($e < h$), la menace est dévaluée :
  $$d_{\text{effective}} = \frac{d_\infty(e, h)}{C(e, h)}$$
- Le « défenseur fantôme » est automatiquement ignoré, restituant le village à notre récolte OFR prioritaire.

---

## 4. Le Dilemme de la Scission : Scission Macroscopique Asymétrique

Sur grande carte ($15 \times 29$), le dogme de l'armée unifiée unique (*Deathball*) perd du temps face à la récolte parallèle, mais autoriser le multi-groupes dans l'Alpha-Beta fait exploser le facteur de branchement ($\ge 64$).

### La Solution d'Argon :
Ne jamais déléguer la scission à la combinatoire microscopique d'Alpha-Beta. La scission doit être gérée **en amont** au niveau macroscopique :
1. **Conditions d'activation** : Active uniquement sur grandes cartes ($> 6$ villages neutres, distance moyenne $> 8$).
2. **Attribution asymétrique des rôles** :
   - **Groupe Alpha (70% des effectifs)** : Maintient le bloc de frappe Lanchester pour la dissuasion et le combat frontal.
   - **Groupe Bêta (Éclaireur, 30% des effectifs)** : Détaché uniquement pour collecter les villages isolés en zone totalement sécurisée ($\Gamma_{VOR} > 0.8$).
3. **Protocole de Réunification d'Urgence** : Dès qu'une armée ennemie approche à $d \le 4$ du Groupe Bêta, celui-ci a pour consigne unique de rallier immédiatement le Groupe Alpha pour reformer le bloc invincible.

---

## 5. Les 3 Clés pour Remporter le Tournoi Final
1. **Évaluation Non-Linéaire à Seuils de Phase** : Valoriser exponentiellement le franchissement du ratio $\ge 1.5\times$ (victoire déterministe garantie).
2. **Principal Variation Search (PVS) + TT-Move Ordering** : Placer le coup issu de la Table de Transposition en premier pour diviser l'arbre par deux, combiné à une recherche à fenêtre nulle (`null window`).
3. **Architecture « Zero-Allocation »** : Pré-calculer statiquement au démarrage toutes les tables de distances de Chebyshev, les voisinages à 8 cases et les masques de Zobrist sous forme de tableaux indexés par $y \cdot \text{width} + x$. Éviter toute création d'objets dans la boucle récursive pour garantir un temps d'exécution $< 1.65\text{s}$.
