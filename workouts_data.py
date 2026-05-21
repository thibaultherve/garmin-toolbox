"""
Source de verite UNIQUE du plan d'entrainement Bedrock + des seances.

Ce fichier sert deux roles :
  1. DOC du plan : tout l'en-tete (commentaires ci-dessous) decrit le plan
     Bedrock complet -- objectifs, profil athlete, zones, contraintes sante,
     cycles, decisions, terrain GPX. Le CLAUDE.md ne couvre que l'infra/toolkit.
  2. DATA des seances : la liste WORKOUTS plus bas, consommee par :
       - generate_fit.py        (genere les .fit pour USB / backup)
       - upload_and_schedule.py (upload via API + schedule au calendrier)

Conventions data :
  - Date au format ISO YYYY-MM-DD
  - Code interne : "C<cycle>-S<sem>-<jour3lettres>-<typeCourt>"
  - Le nom complet final sera "YYYYMMDD_<code>" (fichier et workout API)
  - Steps : kind="step" ou "repeat" (recursif)
  - Targets : "none" | "open" | "hr_zone" (1-5) | "hr_range" (low,high bpm)
              | "power_range" (low,high W) | "power_zone" (1-5)
"""

# =============================================================================
# PLAN BEDROCK -- REFERENCE COMPLETE (source de verite unique)
# =============================================================================
#
# -----------------------------------------------------------------------------
# ETAT ACTUEL (au 04/05/2026)
# -----------------------------------------------------------------------------
# Plan Bedrock demarre 29/04/2026. Baseline complete dans
# data/baseline_2026-04-29.md (a diff en fin de plan ~29/11/2026).
#
# Fait :
#   - Diagnostic 6 derniers mois + 4 GPX terrain analyses + Hill/Endurance
#     Score historiques importes
#   - Cycle 0 (calibration) + Cycle 1 (base aerobie 8 sem) rediges et
#     encodes ci-dessous
#   - Test FCmax 01/05 sur cote_de_corubert : pic 194 bpm, Thibault a explose
#     sans finir -> FCmax retenue 195 (+1 bpm de marge)
#   - Zones FC Garmin calibrees post-test FCmax (methode % HRR) -- valeurs
#     courantes via MCP get_zones_snapshot_tool
#   - Stack data complete (cf. CLAUDE.md pour l'infra)
#   - Snapshot baseline 29/04/2026 sauvegarde
#
# Prochaines actions Claude (au moment voulu) :
#   - Sem 3 du Cycle 1 : appliquer la modif "endurance grimpe" sur LR + trail
#     samedi (cf. section DECISIONS plus bas)
#   - Fin Cycle 1 (~28/06) : bilan complet + redaction Cycle 2 ci-dessous
#   - Fin Cycles 2/3 : idem redaction du cycle suivant
#   - Fin de plan (~29/11/2026) : refaire snapshot baseline + diff complet
#     vs 29/04. Methode/tools listes en section 9 du baseline.
#
# -----------------------------------------------------------------------------
# OBJECTIFS & CIBLES FIN DE PLAN
# -----------------------------------------------------------------------------
# Strategie globale (6 axes du plan) : casser polarisation 8/40/52 -> 80/10/10,
# monter volume 25 -> 45 km/sem, depasser LR 21 km en Z2 strict, structurer
# VO2max, passer a 5 seances/sem, combler gap Hill endurance/strength.
# Detail dans data/baseline_2026-04-29.md.
#
# Cibles metriques fin de plan (etat courant via MCP garmin-coach) :
#   - VO2max         : 56-57
#   - Endurance Score: 7200-7500
#   - Hill Score     : 60+ overall, 50+ endurance
#   - Polarisation   : 80/10/10
#   - Volume         : 50 km/sem soutenu
#   - LR max         : 25-30 km trail vallonne
#
# Test final fin de plan (sem 27, ~22-29/11/2026), sur 7 jours :
#   5K route (seg_lamariette_1300m_plat x4 ~ 5.2km plat) + Hill Score test
#   (cote courte raide) + trail mi-long 25-30 km Perche.
#
# Pas de course objectif : objectif metrique + capacite physique. Test final
# = trail mi-long auto-organise.
#
# -----------------------------------------------------------------------------
# PROFIL ATHLETE
# -----------------------------------------------------------------------------
# Athlete : Thibault, 29 ans, vit a Saint-Jean-de-la-Foret (Perche, Orne 61),
# ~72 kg.
# Coach virtuel : Claude Code, qui pilote la calibration via les data Garmin
# (MCP garmin-coach).
# Hardware : Forerunner 955 + ceinture HR (obligatoire pour Z2 strict + VO2max,
# poignet sur-estime 5-15 bpm en bas de zone). Power running natif FR 955
# (pas de Stryd).
#
# Metriques live (fetcher via MCP avant analyse) :
#   - FCmax/FCrepos/LTHR/floors zones HR+Power : get_zones_snapshot_tool
#   - VO2max + tendance + race predictions + poids : get_fitness_trend_tool
#   - Hill Score (overall+endurance+strength) : get_hill_score_history_tool
#   - Endurance Score : get_endurance_score_history_tool
#   - Fitness Age : get_fitness_age_tool
#   - HRV/RHR/sleep/body battery/readiness : get_daily_recovery_tool
#   - Training Status + monthlyLoad + trainingBalanceFeedbackPhrase :
#     get_training_status_tool
#
# Snapshot pre-plan (frozen 29/04/2026) : data/baseline_2026-04-29.md --
# reference pour comparaison fin de plan, pas pour analyse courante.
#
# -----------------------------------------------------------------------------
# ZONES FC -- SOURCE DE VERITE : GARMIN CONNECT (% HRR)
# -----------------------------------------------------------------------------
# Zones FC definies dans Garmin Connect (Profil > Heart Rate Zones > Running)
# en methode % HRR. Tout le plan + workouts pointent vers les zones par numero
# (hrZ(2) = "ce que Garmin appelle Z2 a l'instant T"). Recalibrage Garmin ->
# tout s'adapte sans toucher au code.
#
# NE JAMAIS coder de bornes BPM en dur dans WORKOUTS ci-dessous, sauf
# intervalles cotes qui chevauchent 2 zones -- preferer alors une zone Garmin
# entiere (hrZ(3) ou hrZ(4)) plutot qu'un range custom.
#
# Bornes BPM live : get_zones_snapshot_tool (a appeler avant toute analyse
# Z2/Z3/Z4 -- Thibault recalibre Garmin apres chaque test, le code suit
# automatiquement via hrZ(n)).
#
# Usage par zone :
#   Z1 recup            50-60% HRR  sub-running pour Thibault, voir mapping
#   Z2 endurance fond.  60-70% HRR  80% du temps Cycle 1 : footings, LR, trail
#   Z3 tempo / SV1      70-80% HRR  tempo Cycle 2, blocs Z3 LR
#   Z4 seuil / SV2      80-90% HRR  cotes longues, intervalles seuil Cycle 2
#   Z5 VO2max           90-100% HRR VO2max Cycle 3, sprints test
#
# LTHR : a re-mesurer via test seuil 30min sem 8 (sam 27/06). Valeur courante
# via get_zones_snapshot_tool (champ lthr). Tant que pas mesure post-test, pas
# de mode % LT cote Garmin.
#
# -----------------------------------------------------------------------------
# CONTRAINTES SANTE / INDIVIDUELLES (ADAPTATIONS PLAN)
# -----------------------------------------------------------------------------
# - Periostite history -> progression volume max +10%/sem, surfaces souples
#   > bitume
# - Syndrome essuie-glace genou (TFL/bandelette) sur trail Perche ->
#   renforcement fessier moyen + technique descente des Cycle 1
# - Decharge cuisse gauche persistante -> echauffement long avant intervalles,
#   monitorer
# - Mal bas du dos chronique (5 ans, suite chute) -> gainage ANTI-ROTATION
#   (pas de crunch/sit-up), mobilite hanches
# - Manque de souplesse -> mobilite 5 min/jour > grands etirements
# - Anti-depresseur leger + chomage en cours + sujet aux crises d'angoisse :
#     - Routine matinale = stabilisateur d'humeur
#     - Pas de double seance, pas de pression perf
# - A jeun-light avant LR : 2 toasts + 1 banane OK jusqu'a 90 min. Au-dela,
#   ajouter glucides a mi-parcours
# - Vomi sur isotonique au trail : c'est l'intensite (Z4-Z5) qui shut down
#   l'estomac, pas la boisson. Regle naturellement par Z2 strict en Cycle 1
# - Pas d'experience marathon ni objectif marathon : on construit endurance
#   via blocs periodises, pas via prepa marathon classique
#
# -----------------------------------------------------------------------------
# PLAN D'ENTRAINEMENT
# -----------------------------------------------------------------------------
# Modele : periodisation en blocs polarisee 80/20, pilotee a la FC (allure
# useless en Perche).
#
# Vue d'ensemble -- 24 semaines / 4 cycles :
#   Cycle 0   5 jours   29/04 -> 03/05  Calibration + test FCmax  ~15 km
#   Cycle 1   8 sem     04/05 -> 28/06  Base aerobie              33 -> 45 km/sem
#   Cycle 2   6+1 sem   06/07 -> 23/08  Seuil lactique            40-50 km/sem
#   Cycle 3   5+1 sem   31/08 -> 11/10  VO2max (cible 56+)        40-50 km/sem
#   Cycle 4   5+1 sem   19/10 -> 29/11  Trail specifique + bilan  45-55 km/sem
#
# Decharge -30% volume entre chaque cycle. Tests fin de cycle (FC seuil,
# 5K TT, VO2max test, trail mi-long).
#
# Cycle 1 -- type-semaine (EN COURS, encode ci-dessous) :
#   LUN  Footing Z2 court ou repos selon ressenti
#   MAR  Footing Z2 strict (50-60 min)
#   MER  Cotes (sur cote courte pentue, formats variables)
#   JEU  Footing Z2 court + muscu/mobilite 30 min
#   VEN  Footing Z2 strict (40-50 min)
#   SAM  Footing Z2 (60-80 min, route)
#   DIM  Sortie longue trail Z2 progressive (75 -> 120 min, chemins Perche)
#        Switch 13/05/2026 : la LR migre du dimanche-route au dimanche-trail.
#        Specificite trail-Bedrock + impact mecanique plus bas en LR longue.
#
# Cibles dans les workouts -- mapping intentions -> target :
#   Echauffement, cooldown, recup intervalles  -> hrZ(2)
#       Z1 inatteignable en courant pour Thibault, la montre beeperait en
#       permanence. Sur recup courte d'intervalles, FC ne redescend pas sous
#       Z2 de toute facon.
#   Footings, LR, trail facile (Z2 strict)     -> hrZ(2)
#       Base aerobie, allure s'auto-regule selon terrain.
#   Bloc Z3 en LR (Cycle 2+, allure marathon)  -> hrZ(3)
#       Tempo leger.
#   Cotes courtes 40-60s "Z3-haut, dynamique"  -> hrZ(3)
#       FC deborde naturellement en Z4 sur les dernieres secondes -- c'est OK,
#       on ne pilote pas la FC sur 40s.
#   Cotes longues 90s-3min "Z4 controle"       -> hrZ(4)   (seuil-bas)
#   Tempo / cruise intervals (Cycle 2)         -> hrZ(4)   (seuil)
#   VO2max 3-5min (Cycle 3)                    -> hrZ(5) ou OPEN()
#       On push, peu importe la borne basse.
#   Test FCmax / 5K TT / test seuil 30min      -> OPEN()
#       On push, la montre ne beep pas.
#   Strides courts (lignes droites 30s)        -> OPEN()
#       Trop court pour qu'une cible FC soit pertinente.
#
# Cycles 2 / 3 / 4 -- pas encore encodes :
#   Templates detailles dans plan_training_bedrock.txt (seances jour par
#   jour). A recalibrer apres bilan fin Cycle 1 + test FC seuil 27/06 avant
#   ecriture finale ci-dessous.
#
# Logique de transition entre cycles :
#   - 1 sem decharge entre chaque cycle (-30 a -40% volume), sauf si fatigue
#     -> +1 sem
#   - Recalibrage zones FC apres chaque test de fin de cycle
#   - Si Hill endurance ne progresse pas -> ajouter 1 LR vallonne/sem dans
#     le cycle suivant
#   - Si Training Status reste "Maintaining" -> augmenter volume Z2 de
#     10-15% avant intensite
#
# -----------------------------------------------------------------------------
# BOUCLE D'ANALYSE POST-SEANCE
# -----------------------------------------------------------------------------
# Le plan n'est PAS fige -- il est ajuste a mesure que les data arrivent.
#
# Quand Thibault demande "analyse ma sortie" / "bilan de la semaine" :
#
# 1. Recuperer les data fraiches via MCP garmin-coach. Toujours commencer par
#    get_zones_snapshot_tool pour avoir les bornes BPM live, puis
#    get_last_activity_tool / get_activity_details_tool / get_daily_recovery_tool
#    / get_training_status_tool / get_weekly_load_summary_tool /
#    get_hill_score_history_tool selon le besoin.
#
# 2. Comparer aux cibles du plan :
#    - Footing Z2 bien dans Z2 ou derive en Z3 ?
#    - Drift FC sur LR : <5% OK, >8% trop rapide/long
#    - Volume hebdo conforme a +10%/sem max ? (ponderer par stress, pas
#      seulement km -- cf. memory feedback_volume_intensity_equivalence)
#    - Polarisation cumulee 7j se rapproche de 80/10/10 ?
#    - HRV stable ou en baisse > 10% vs ligne de base ?
#    - Hill endurance progresse vers cible Cycle 1 ?
#
# 3. Decider d'un ajustement (uniquement si pertinent) :
#    - Sensations bonnes + metriques coherentes -> continuer le plan
#    - HRV en chute, sommeil degrade -> decharge anticipee
#    - Z2 systematiquement depasse en Z3 -> recalibrer dans Garmin (puis
#      re-fetch get_zones_snapshot_tool)
#    - Cotes trop faciles/dures -> ajuster reps ou recup
#    - LR difficile (drift > 8%) -> reduire la sortie longue suivante de
#      10-15 min
#    - VO2max stagne > 3 sem -> verifier polarisation
#    - Hill endurance stagne apres sem 4 -> intensifier climbing
#    - Blessure ou douleur -> adapter (cf. contraintes sante)
#
# 4. Si ajustement : modifier WORKOUTS ci-dessous, regenerer .fit, re-push
#    avec --replace. Documenter dans la section DECISIONS.
#
# Cadence d'analyse : apres seance test (FCmax, seuil, premieres VO2max,
# premier LR > 100 min) = analyse approfondie. Fin de semaine (dimanche soir)
# = bilan rapide. Fin de cycle = analyse complete + recalibrage zones +
# livraison cycle suivant.
#
# Garde-fous (ne PAS sur-reagir) :
#   - 1 seule seance degradee ne justifie pas un changement
#   - Tendance sur 3-5 seances = signal legitime
#   - Privilegier la simplicite : ajuster 1-2 elements a la fois
#   - Le plan est une boussole, pas une loi : swap ou skip est OK le jour J
#
# -----------------------------------------------------------------------------
# DECISIONS IMPORTANTES
# -----------------------------------------------------------------------------
# Choix structurels (immuables sauf desaccord explicite de Thibault) :
#   - Cibles HR vs allure : sur le Perche vallonne, l'allure est INUTILE.
#     Tout est pilote a la FC.
#   - Ceinture HR obligatoire sur Z2 strict et VO2max (poignet sur-estime de
#     5-15 bpm en bas de zone, retard 10-15s sur demarrages d'intervalles).
#   - Pas de cycle marathon classique : objectif VO2max + trail. LR plafonne
#     22-25 km au lieu de 32 km.
#   - Test FCmax sem 0 + Test FC seuil fin Cycle 1 (sam 27/06) pour
#     recalibrer Z3/Z4 avant Cycle 2.
#   - Format date YYYYMMDD en prefixe + code C<cycle>-S<sem>-<jour3lettres>-
#     <typeCourt> (ex. C1-S1-Mer-Cotes6x40s)
#   - Pas de muscu en .fit Garmin : la seance muscu jeudi reste dans le
#     plan papier.
#
# Modif endurance grimpe (decidee 29/04/2026, a appliquer en sem 3 du Cycle 1)
#   Constat (baseline 29/04/2026) : Hill Score endurance stagne tres bas vs
#   strength (gap creuse depuis dec 2025). Aucune sortie n'inclut de climbing
#   soutenu -- toutes les cotes Cycle 1 sem 1-5 sont courtes (40-60s).
#   Etat courant via get_hill_score_history_tool.
#
#   Modif a appliquer a partir de sem 3 :
#     - Trail samedi (sem 3+) : ajouter notes "choisir parcours avec >=1
#       montee soutenue 5+ min, Z2 haut -> bas Z3 acceptable en montee,
#       marcher 30s si pic Z4+".
#     - LR dimanche (sem 5+) : "inclure 2 montees soutenues 3-5 min sur
#       cote_douce ou equivalent, Z2-haut -> bas Z3 acceptable en montee".
#
#   Pourquoi pas avant sem 3 : sem 1-2 = focus Z2 strict pur post-FCmax.
#
#   Cible mesurable : Hill ENDURANCE +6 pts vs baseline 29/04 fin Cycle 1
#   (sem 8). Tracker via get_hill_score_history_tool chaque fin de semaine.
#
#   Si stagne apres sem 4 : intensifier (cotes longues plus tot en Cycle 2).
#
# -----------------------------------------------------------------------------
# TERRAIN -- GPX + COTES
# -----------------------------------------------------------------------------
# 4 GPX de reference (data/gpx/) :
#   cote_courte_pentu.gpx          ~400 m,  +38 m, 9.5% (12% final)
#       -> Hill reps 30-90s, strides explosifs, Hill Score test
#   cote_douce.gpx                 ~1250 m, +52 m, 4.2%
#       -> Hill reps 2-3 min, tempo en montee
#   cote_de_corubert.gpx           ~1200 m, +59 m, 4.9% moy, mur 12-13%
#                                                            km 0.95-1.05
#       -> Test FCmax (ramp progressif), hill reps longues, montee approchee
#          par autre versant que cote_courte_pentu (meme sommet ~243 m)
#   seg_lamariette_1300m_plat.gpx  ~1350 m one-way, ~1% (14 m amplitude)
#       -> Test seuil 30 min, tempo, test 5K
#
# Boucles de footing analysees :
#   mariette_classique.gpx (~5.5 km, +70 m) : boucle Z2 facile 40 min,
#       traverse la portion haute de cote_courte_pentu
#   parcours_vendredi_testfcmax.gpx (~7.7 km, +117 m, boucle) : parcours du
#       test FCmax 01/05 -- echauf km 0-4 (descente -10% au km 2.6 attention
#       TFL), test cote_de_corubert km 4-5.6, retour descendant km 5.6-7.7
#
# Sortie 13K du 26/04 (activity_id 22663914025) = parcours trail facile par
# defaut.
#
# Decouverte exhaustive de cotes : voir discover_climbs.py (catalog dans
# data/climbs/, doc dans data/climbs/README.md). Sert a trouver des cotes
# inconnues qui matchent une intention d'entrainement (ex. "cotes 3-5 min
# sustained a 5-8% pour endurance grimpe sem 3+").
#
# =============================================================================


def s(name, dur, **kw):
    """Helper pour creer un step (raccourci)."""
    d = {"kind": "step", "name": name, "duration_min": dur}
    d.update(kw)
    return d


def rep(iters, *steps):
    """Helper pour creer un bloc repete."""
    return {"kind": "repeat", "iterations": iters, "steps": list(steps)}


# Targets reutilisables
def hrZ(z): return {"type": "hr_zone", "zone": z}
def hrR(low, high): return {"type": "hr_range", "low": low, "high": high}
def pwr(low, high): return {"type": "power_range", "low": low, "high": high}
def OPEN(): return {"type": "open"}
def NONE(): return {"type": "none"}


# =============================================================================
# CATALOGUE DES SEANCES
# =============================================================================

WORKOUTS = []

# -----------------------------------------------------------------------------
# CYCLE 0 - CALIBRATION (Mer 29/04 -> Dim 03/05)
# -----------------------------------------------------------------------------
# 5 jours pour : tester ceinture HR, comparer poignet/ceinture, faire test FCmax
# qui calibre les zones definitives pour Cycle 1.

WORKOUTS.append({
    "date": "2026-04-29",
    "code": "C0-Mer-Calib-40min",
    "description": "Premiere sortie ceinture HR. Z2 strict 40min, comparer ceinture vs poignet.",
    "steps": [
        s("Echauf", 5, type="warmup", target=hrZ(2), notes="trotting tres lent"),
        s("Z2 strict", 30, type="active", target=hrZ(2),
          notes="ceinture obligatoire. Marche si Z3"),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-01",
    "code": "C0-Ven-TestFCmax",
    "description": "Test FCmax sur cote_de_corubert (mur 13% km 5.0-5.1) - boucle 7.7km +117m. 1 montee full ramp.",
    "steps": [
        s("Echauf", 28, type="warmup", target=hrZ(2),
          notes="km 0-4 du parcours: ondulation douce puis descente. ATTENTION descente -10% km 2.6-2.8 = pas technique pour le TFL. Finir au pied de cote_de_corubert (km 4.0)."),
        s("Strides", 2, type="warmup", target=OPEN(),
          notes="2 lignes droites 30s allure rapide au pied de la cote, reveil vitesse"),
        s("Montee FULL", 9, type="interval", target=OPEN(),
          notes="km 4.0 a 5.6: 0-900m faux-plat 2-5% tempo Z3-Z4 bas / 900m approche / MUR 12-13% sur 100m ALL-OUT / replat + relance 7% finale SPRINT. NE PAS COUPER LA MONTRE au sommet, FCmax pique 5-10s apres arret."),
        s("Retour", 14, type="cooldown", target=hrZ(2),
          notes="km 5.6 a 7.7: descente progressive jusqu a chez soi, FC<130, derouler les jambes"),
    ],
})

WORKOUTS.append({
    "date": "2026-05-03",
    "code": "C0-Dim-LR-60min",
    "description": "Sortie longue Z2 reduite 60min, recup post-test.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 45, type="active", target=hrZ(2),
          notes="zones recalibrees apres test FCmax"),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# CYCLE 1 - BASE AEROBIE (8 sem, 04/05 -> 28/06) - 28 km/sem -> 45 km/sem
# -----------------------------------------------------------------------------
# Objectif : casser polarisation 8/40/52, atteindre 70/15/15 fin de cycle.
# Type-semaine : Mar Z2 / Mer cotes / Ven Z2 / Sam trail Z2 / Dim LR Z2

# -----------------------------------------------------------------------------
# SEMAINE 1 (04 - 10/05) - ADAPTEE: SAM+DIM voyage indispo, LR avance au VEN
# Volume cible 22-30 km (vs 33 km plan original)
# Chaine DIM(LR fait) -> LUN -> MAR -> MER = 4 jours d'affilee, MAR conditionnel
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-05-04",
    "code": "C1-S1-Lun-Z2-40min",
    "description": "Footing Z2 doux 40min, recup active post-LR DIM. Allure tres conservative. ~5.5 km. Skip si mental KO (lundi normalement OFF sacre).",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 doux", 25, type="active", target=hrZ(2),
          notes="respiration nasale comme test (si possible = vraie Z2). Tres doux."),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-05",
    "code": "C1-S1-Mar-Z2-50min",
    "description": "Footing Z2 50min CONDITIONNEL (J+2 chaine 4j). Go si HRV>=60ms ET BB>=60 ET sommeil>=70 ET jambe gauche neutre. Sinon OFF. ~7.5 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 35, type="active", target=hrZ(2),
          notes="ralentir si Z3, marche en cote si necessaire"),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-06",
    "code": "C1-S1-Mer-Cotes6x40s",
    "description": "Cotes douces 6x40s bas cote courte pentue (200m, 6-7%). HRV check matin (>=60ms). Echauf+retour: lap-button. Reps 40s + recup 1.5min: fixes (~5.9 km estime).",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(6,
            s("Cote 40s", 0.67, type="interval", target=hrZ(3),
              notes="cible Z3, foulee dynamique. FC peut deborder Z4 sur dernieres sec - OK."),
            s("Recup", 1.5, type="recovery", target=hrZ(2),
              notes="redescente marche, retour Z2")),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-05-08",
    "code": "C1-S1-Ven-LR-75min",
    "description": "LR Z2 75min avance du DIM (voyage WE). Premiere LR cycle 1, allongee de 10min car S1 sous-volume vs S2. Allure conservative, marche si cote Z3. ~11.5 km @6:30/km.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2)),
        s("Z2 LR", 55, type="active", target=hrZ(2),
          notes="bas du Z2 ideal, marche si cote Z3"),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# SAM 09/05 + DIM 10/05 : voyage, OFF imposes (rien a programmer)

# -----------------------------------------------------------------------------
# SEMAINE 2 (11 - 17/05) - 32 km
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-05-11",
    "code": "C1-S2-Lun-Z2-55min",
    "description": "Footing Z2 strict 55min - reactivation post-WE voyage (swap lun<->mar pour casser chaine 3j OFF). ~8.5 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 40, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-13",
    "code": "C1-S2-Mer-Cotes8x40s",
    "description": "Cotes 8x40s bas cote courte pentue (200m, 6-7%). Echauf+retour: lap-button. Reps 40s + recup 1.5min: fixes (~6.5 km estime).",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(8,
            s("Cote 40s", 0.67, type="interval", target=hrZ(3),
              notes="cible Z3, foulee dynamique. FC peut deborder Z4 sur dernieres sec - OK."),
            s("Recup", 1.5, type="recovery", target=hrZ(2),
              notes="redescente marche, retour Z2")),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-05-15",
    "code": "C1-S2-Ven-Z2-45min",
    "description": "Footing Z2 strict 45min. ~6.9 km @6:30/km.",
    "steps": [
        s("Echauf", 8, type="warmup", target=hrZ(2)),
        s("Z2 strict", 32, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-16",
    "code": "C1-S2-Sam-Z2-65min",
    "description": "Footing Z2 65min (route). ~10.0 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 trail", 50, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})
# REALISE 2026-05-16 : seance prescrite NON FAITE. Remplacee par un blabla
# run trail en foret avec un pote (chemins + crapahutage), sans regarder
# montre / FC / allure -- conduit au "flow".
# Realise : 73min, 10.25km, D+237m, HR avg 145 (max 171), pace 7:03 / GAS 6:42,
# Z2 45.8% / Z3+Z4 32.8%, TE aero 3.3, label AEROBIC_BASE, TL 96.
# Drift FC inverse -0.46%, decoupling Pa:HR +2.74% (OK <5% Friel).
# Cf. data/activities/2026-05-16_id22898927334.json pour le dump complet.

WORKOUTS.append({
    "date": "2026-05-17",
    "code": "C1-S2-Dim-Trail-LR-85min",
    "description": "Sortie longue trail Z2 85min (chemins), +20min vs sem 1. ~13.1 km @6:30/km.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2)),
        s("Z2 LR", 65, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# SEMAINE 3 (18 - 24/05) - 36 km
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-05-19",
    "code": "C1-S3-Mar-Z2-55min",
    "description": "Footing Z2 strict 55min. ~8.5 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 40, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})
# REALISE 2026-05-19 : seance prescrite NON SUIVIE (workout uploade ignore,
# run "free" "Belleme Running"). Remplacee par blabla run plat avec un pote.
# Realise : 60.2min, 9.06km, D+66m/D-66m (7.3m/km, plat confirme),
# pace avg 6:34/km (6:21-7:19 en negative split km4->km9 : 6:36->6:21),
# HR avg 128 / max 145, Z1 86.7% / Z2 13.3% (vs Z2 strict prescrit 136-150),
# TE aero 2.7, label AEROBIC_BASE, TL 58 (vs ~75 attendus).
# Decoupling Pa:HR -2.64% (negatif, base aerobie solide), HR drift +0.33%
# (quasi nul), EF half1->half2 1.179->1.210 (efficacite intra-seance ++).
# Verdict : pas un Z2 (14 bpm sous baseline Z2 142 habituelle) mais
# Z1 conversationnel propre -- stim aerobie moindre mais signature
# d'adaptation aerobie excellente. Meteo : 16-17C, vent 22-25 km/h
# rafales 55-57 km/h SO, sans impact FC visible.
# Cf. data/activities/2026-05-19_id22937165875.json pour le dump complet.

WORKOUTS.append({
    "date": "2026-05-20",
    "code": "C1-S3-Mer-Cotes8x60s",
    "description": "Cotes 8x60s sur cote courte pentue (montee plus haute, ~250m). Echauf+retour: lap-button.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(8,
            s("Cote 60s", 1.0, type="interval", target=hrZ(3),
              notes="RPE 8/10 hard foulee tonique. Fin de rep : puis-je refaire un comme ca? Oui sur 7, juste sur 8e = pacing parfait."),
            s("Recup", 2.0, type="recovery", target=hrZ(2))),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-05-22",
    "code": "C1-S3-Ven-Trail-LR-85min",
    "description": "Sortie longue trail Z2 85min (chemins). ~13 km @6:30/km.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2)),
        s("Z2 LR", 65, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-23",
    "code": "C1-S3-Sam-Z2-70min",
    "description": "Footing Z2 70min (route). ~10.8 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 trail", 55, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-24",
    "code": "C1-S3-Dim-Z2-57min",
    "description": "Footing Z2 strict 57min. ~8.7 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 42, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# SEMAINE 4 (25 - 31/05) - 28 km - DECHARGE
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-05-26",
    "code": "C1-S4-Mar-Z2-40min",
    "description": "DECHARGE - Footing Z2 court 40min. ~6.2 km @6:30/km.",
    "steps": [
        s("Echauf", 8, type="warmup", target=hrZ(2)),
        s("Z2 strict", 27, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-27",
    "code": "C1-S4-Mer-Cotes5x60s",
    "description": "DECHARGE - Cotes allegees 5x60s. Echauf+retour: lap-button.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(5,
            s("Cote 60s", 1.0, type="interval", target=hrZ(3),
              notes="Decharge - RPE 7/10 max. Sortir frais, pas essouffle. 1 cran sous S3, on retient."),
            s("Recup", 2.0, type="recovery", target=hrZ(2))),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-05-29",
    "code": "C1-S4-Ven-Z2-35min",
    "description": "DECHARGE - Footing Z2 court 35min. ~5.4 km @6:30/km.",
    "steps": [
        s("Echauf", 5, type="warmup", target=hrZ(2)),
        s("Z2 strict", 25, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-05-31",
    "code": "C1-S4-Dim-Trail-LR-70min",
    "description": "DECHARGE - LR trail reduit 70min (chemins). ~10.8 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 LR", 55, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# SEMAINE 5 (01 - 07/06) - 38 km - reprise progressive
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-06-02",
    "code": "C1-S5-Mar-Z2-60min",
    "description": "Footing Z2 strict 60min. ~9.2 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 45, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-03",
    "code": "C1-S5-Mer-Cotes10x60s",
    "description": "Cotes 10x60s, premiere fois 10 reps. Echauf+retour: lap-button.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(10,
            s("Cote 60s", 1.0, type="interval", target=hrZ(3),
              notes="10 reps - pacing critique. RPE 7-8 sur 7 premiers, monter 8-9 sur 3 derniers. Si rep 4 fait deja mal = trop fort, ralentir."),
            s("Recup", 2.0, type="recovery", target=hrZ(2))),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-06-05",
    "code": "C1-S5-Ven-Z2-50min",
    "description": "Footing Z2 strict 50min. ~7.7 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 35, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-06",
    "code": "C1-S5-Sam-Z2-75min",
    "description": "Footing Z2 75min (route). ~11.5 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 trail", 60, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-07",
    "code": "C1-S5-Dim-Trail-LR-100min",
    "description": "Sortie longue trail Z2 100min (chemins), cap des 100min. ~15.4 km @6:30/km.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2)),
        s("Z2 LR", 80, type="active", target=hrZ(2),
          notes="banane si jambes lourdes a mi-parcours"),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# SEMAINE 6 (08 - 14/06) - 42 km - intro premier bloc Z3 en LR
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-06-09",
    "code": "C1-S6-Mar-Z2-60min",
    "description": "Footing Z2 strict 60min. ~9.2 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 45, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-10",
    "code": "C1-S6-Mer-Cotes6x90s",
    "description": "Cotes 6x90s, montees plus longues. Echauf+retour: lap-button.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(6,
            s("Cote 90s", 1.5, type="interval", target=hrZ(4),
              notes="RPE 7-8/10 sustained, respiration cadencee 2-2. Mi-rep (45s) : puis-je tenir 45s de plus meme pace? Oui ferme = bon. A peine = trop fort."),
            s("Recup", 2.5, type="recovery", target=hrZ(2))),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-06-12",
    "code": "C1-S6-Ven-Z2-50min",
    "description": "Footing Z2 strict 50min. ~7.7 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 35, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-13",
    "code": "C1-S6-Sam-Z2-75min",
    "description": "Footing Z2 75min (route). ~11.5 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 trail", 60, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-14",
    "code": "C1-S6-Dim-Trail-LR-110min-Z3",
    "description": "LR trail 110min (chemins) avec premier bloc 10min Z3 milieu de course. ~16.9 km @6:30/km.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2)),
        s("Z2 debut", 50, type="active", target=hrZ(2)),
        s("Bloc Z3", 10, type="interval", target=hrZ(3),
          notes="sur portion roulante, allure marathon"),
        s("Z2 fin", 30, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# SEMAINE 7 (15 - 21/06) - 45 km - PIC
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-06-16",
    "code": "C1-S7-Mar-Z2-60min",
    "description": "Footing Z2 strict 60min. ~9.2 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 45, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-17",
    "code": "C1-S7-Mer-Cotes6x2min",
    "description": "Cotes 6x2min sur cote douce (4-5%, ~600m). Premier bloc seuil court. Echauf+retour: lap-button.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2), duration_open=True,
          notes="2.65km jusqu'au pied de la cote. Lap pour demarrer rep 1."),
        rep(6,
            s("Cote 2min", 2, type="interval", target=hrZ(4),
              notes="RPE 7/10 cruise inconfortable. Tu finis chaque rep en pensant 'j'aurais pu 30s de plus'. On retient, on ne pousse PAS comme sur les courtes - premier bloc seuil."),
            s("Recup", 3, type="recovery", target=hrZ(2),
              notes="redescente marche/trot")),
        s("Retour", 10, type="cooldown", target=hrZ(2), duration_open=True,
          notes="2.65km retour domicile. Lap pour fin de seance."),
    ],
})

WORKOUTS.append({
    "date": "2026-06-19",
    "code": "C1-S7-Ven-Z2-55min",
    "description": "Footing Z2 strict 55min. ~8.5 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 strict", 40, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-20",
    "code": "C1-S7-Sam-Z2-80min",
    "description": "Footing Z2 80min (route). ~12.3 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 trail", 65, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-21",
    "code": "C1-S7-Dim-Trail-LR-120min",
    "description": "LR trail 120min Z2 (chemins) - pic du cycle 1, max 2h. ~18.5 km @6:30/km.",
    "steps": [
        s("Echauf", 15, type="warmup", target=hrZ(2)),
        s("Z2 LR", 100, type="active", target=hrZ(2),
          notes="banane mi-parcours, eau pure"),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

# -----------------------------------------------------------------------------
# SEMAINE 8 (22 - 28/06) - 30 km - DECHARGE + TEST FC SEUIL
# -----------------------------------------------------------------------------

WORKOUTS.append({
    "date": "2026-06-23",
    "code": "C1-S8-Mar-Z2-40min",
    "description": "DECHARGE - Footing Z2 court 40min. ~6.2 km @6:30/km.",
    "steps": [
        s("Echauf", 8, type="warmup", target=hrZ(2)),
        s("Z2 strict", 27, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-26",
    "code": "C1-S8-Ven-Z2-30min",
    "description": "DECHARGE - Footing Z2 tres court 30min, jambes legeres. ~4.6 km @6:30/km.",
    "steps": [
        s("Echauf", 5, type="warmup", target=hrZ(2)),
        s("Z2 strict", 20, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-27",
    "code": "C1-S8-Sam-TestSeuil30min",
    "description": "TEST FC SEUIL Friel 30min. Route semi-plate, ceinture HR obligatoire. LTHR = FC moy du step 'TT Plateau 20min'.",
    "steps": [
        s("Echauf Z2", 10, type="warmup", target=hrZ(2),
          notes="progressif Z1->Z2"),
        s("Echauf Z3", 5, type="warmup", target=hrZ(3),
          notes="finir chaud en Z3 ~85% FCmax. Crucial : FC deja sur plateau au depart TT"),
        s("TT Build 10min", 10, type="interval", target=OPEN(),
          notes="negative split : RPE 7 -> RPE 8. NE PAS partir comme un 5K. Ce segment n'entre PAS dans le calcul LTHR."),
        s("TT Plateau 20min", 20, type="interval", target=OPEN(),
          notes="RPE 8 stable, finir RPE 8.5 sur min 15-20. *** FC MOY DE CE STEP = LTHR Friel ***. Drift <5bpm = test valide, >8bpm = re-test."),
        s("Retour", 10, type="cooldown", target=hrZ(2)),
    ],
})

WORKOUTS.append({
    "date": "2026-06-28",
    "code": "C1-S8-Dim-Trail-LR-60min",
    "description": "LR trail recup post-test 60min Z2 (chemins). ~9.2 km @6:30/km.",
    "steps": [
        s("Echauf", 10, type="warmup", target=hrZ(2)),
        s("Z2 LR", 45, type="active", target=hrZ(2)),
        s("Retour", 5, type="cooldown", target=hrZ(2)),
    ],
})


# =============================================================================
# Helpers de naming
# =============================================================================

def full_name(workout):
    """Nom complet : 20260429_C0-Mer-Calib-40min"""
    return f"{workout['date'].replace('-', '')}_{workout['code']}"


def short_name(workout, max_len=15):
    """Nom court pour affichage montre (FIT workout_name)."""
    mmdd = workout['date'][5:].replace('-', '')  # MMDD
    parts = workout['code'].split('-')
    short = f"{mmdd} {parts[0]}{parts[1][:3] if len(parts) > 1 else ''}{parts[-1][:6] if len(parts) > 2 else ''}"
    return short[:max_len]


if __name__ == "__main__":
    print(f"{len(WORKOUTS)} workouts definis :\n")
    for w in WORKOUTS:
        print(f"  {full_name(w):42s}  ({short_name(w)})")
