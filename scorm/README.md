# Modules SCORM de sensibilisation (FR)

Trois modules SCORM 1.2, en français, d'environ 15 minutes chacun. Chacun se termine par un quiz noté (80 % pour valider).

| Paquet | Module | Contenu |
|---|---|---|
| `dist/01-phishing.zip` | Reconnaître et déjouer le phishing | **Vidéo de 2 min** (voix off + sous-titres FR), signaux d'alerte, lecture d'URL, e-mail interactif (6 indices), mises en situation, quiz |
| `dist/02-mots-de-passe.zip` | Mots de passe et double authentification | Phrases de passe, testeur de robustesse (local), gestionnaire, MFA et ses pièges, mises en situation, quiz |
| `dist/03-reflexes-quotidien.zip` | Les bons réflexes cyber au quotidien | Poste de travail, USB, nomadisme / Wi-Fi, classification des données, shadow IT et IA, ingénierie sociale, signalement d'incident, quiz |

## Construire

```bash
python3 scorm/build.py            # -> scorm/dist/*.zip (+ scorm/build/<module>/ pour l'aperçu local)
```

Pour l'aperçu local, ouvrez `scorm/build/<module>/start.html` dans un navigateur. Sans LMS, la progression n'est pas enregistrée.

La vidéo (`courses/01-phishing/media/`) est générée à partir de `video/make_video.py`. Les images sont dessinées avec Pillow, la voix est synthétisée par Piper (`fr_FR-siwis-medium`) et le tout est encodé avec ffmpeg :

```bash
docker build -t vidi-scorm-video scorm/video
docker run --rm -u $(id -u):$(id -g) -v "$PWD/scorm/video":/src:ro \
  -v "$PWD/scorm/courses/01-phishing/media":/out vidi-scorm-video python3 /src/make_video.py /out
# PREVIEW=1 (-e PREVIEW=1) : une image PNG par scène au lieu de la vidéo
```

Images de couverture (1280×720) dans `covers/` : `cover-course.png` pour la carte du cours (champ *Image* du cours), et une image par module. Pour les régénérer :

```bash
docker run --rm -u $(id -u):$(id -g) -v "$PWD/scorm/video":/src:ro \
  -v "$PWD/scorm/covers":/out vidi-scorm-video python3 /src/make_covers.py /out
```

## Importer dans Frappe LMS

⚠️ **N'utilisez pas « Importer un cours »** : ce menu attend une archive d'export Frappe qui contient un `course.json` (sinon : *Invalid course ZIP: Missing course.json*). Un paquet SCORM s'ajoute **en tant que chapitre** :

1. Créez le cours (ou ouvrez-le), puis allez dans son plan.
2. **Ajouter un chapitre** → cochez **SCORM Package**.
3. Envoyez le `.zip` du module, puis enregistrez.

## Suivi LMS (SCORM 1.2)

- `cmi.core.lesson_status` : `incomplete`, puis `passed` ou `failed` selon le score du quiz. Frappe ne marque la leçon terminée que sur `passed`.
- `cmi.core.score.raw` : le score du quiz en %. `cmi.interactions.n.*` : une entrée par question.
- `cmi.suspend_data` : signet en JSON (diapositive en cours, activités faites). C'est le seul champ que Frappe conserve pour la reprise.
- Les diapositives « vidéo », « exercice » et « quiz » bloquent le bouton *Suivant* tant que l'activité n'est pas faite.
- Le point d'entrée est `start.html` et non `index.html`. Le nginx de Frappe réécrit `…/index.html` en `…/<chapitre>` (sans `/` final), ce qui casse tous les chemins relatifs (CSS, JS, vidéo).
- `build.py` reprend le filtre anti-code malveillant de Frappe : il refuse les handlers `on…=""` en ligne, `eval(`, `Function(`, `atob`/`btoa` et les scripts externes, pour qu'un paquet ne soit jamais rejeté à l'envoi.
