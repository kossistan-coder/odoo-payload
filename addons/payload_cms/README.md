# Payload CMS pour Odoo (`payload_cms`)

Un CMS headless dans Odoo 18 qui reproduit [Payload CMS](https://payloadcms.com) (v3.90) :

- **Admin sur `/admin`** avec la même interface que Payload (thème clair) : dashboard, navigation, vues liste, édition, versions, API, compte et login. L'UI utilise les **feuilles SCSS originales de Payload** (licence MIT), compilées telles quelles. Les classes CSS et la structure HTML sont celles de Payload, ce qui donne le même rendu.
- **API REST compatible Payload sur `/api`** : un frontend Next.js, Astro ou autre écrit pour Payload peut s'y brancher.
- **Collections, globals et champs** déclarés depuis le backend Odoo (menu *CMS → Configuration*) ou en code, avec des dictionnaires au format `payload.config.ts`.

## Fonctionnalités

| Payload | Implémentation |
|---|---|
| Dashboard (cartes par groupe, bouton « + ») | ✅ |
| Liste : recherche, colonnes (drag & drop), filtres (where builder et/ou), tri, pagination, per page, sélection multiple, publication, dépublication et suppression groupées | ✅ |
| Édition : champs principaux et sidebar, onglets Edit / Versions / API, statut Draft / Published / Changed, Save Draft, Publish changes, menu « … » (Create New, Duplicate, Delete, Unpublish), « Revert to published », garde « Leave without saving », Ctrl+S | ✅ |
| Brouillons, **autosave** et **versions** (liste, comparaison avec diff, « Restore this version » ou « Restore as draft ») | ✅ |
| **Slug auto-généré** (champ verrouillé qui suit le titre, boutons Unlock / Lock / Generate, unicité) | ✅ |
| **Upload** : dropzone, image sizes générées côté serveur (Pillow), recadrage et **focal point** (Edit Image), champ upload (Create New / Choose from existing / drag & drop) | ✅ |
| **Live Preview** : iframe, breakpoints, dimensions, zoom, ouverture dans une nouvelle fenêtre, protocole `postMessage` de `@payloadcms/live-preview` | ✅ |
| **Éditeur Lexical** (Lexical 0.50, comme Payload 3.90) : toolbar flottante, menu « / », poignées « + » et drag, liens (drawer « Edit Link », liens internes), upload et relation dans le texte, listes et check-lists, citations, HR, raccourcis markdown. Le JSON produit est celui de Payload. | ✅ |
| Types de champs : text, textarea, email, number, checkbox, date, select (hasMany), radio, richText, upload, relationship (hasMany), json, code, slug, array, group, blocks, row, collapsible, tabs | ✅ |
| Globals (Header, Footer…) | ✅ |
| Users (`res.users` du groupe « Payload CMS »), compte, changement de mot de passe | ✅ |
| Auth API : login / logout / me / refresh-token (JWT), session Odoo, **clés API Odoo** | ✅ |
| Localisation, GraphQL, hooks, access control par fonction | ❌ pas encore |

## Architecture

```text
payload_cms/
├── controllers/
│   ├── api.py            # API REST Payload (/api/...)
│   ├── admin.py          # SPA /admin et page de preview intégrée /cms/preview/...
│   └── utils.py          # JWT HS256, CORS, réponses JSON
├── models/
│   ├── cms_collection.py         # CollectionConfig / GlobalConfig (+ _sync_schema code-first)
│   ├── cms_field_definition.py   # champs récursifs (array, group, blocks, tabs…)
│   └── cms_document.py           # documents (JSONB), versions, uploads, sérialisation
├── tools/
│   ├── schema.py         # défauts, validation, slugify, population des relations
│   ├── query.py          # where / sort Payload → SQL JSONB
│   └── default_schema.py # collections par défaut (Pages, Posts, Media + Users, globals Header, Footer)
├── views/                # configuration côté Odoo, menus, templates QWeb des pages
└── static/
    ├── admin_src/        # build CSS : SCSS Payload (vendored) + Tailwind CSS v4
    ├── dist/admin.css    # CSS compilée (commitée)
    ├── lib/lexical/      # bundle Lexical 0.50 (window.PayloadLexical)
    ├── src/admin/        # SPA OWL : core/, components/, fields/, richtext/, views/
    └── src/preview/      # frontend de démonstration (preview et live preview)
```

Les documents sont stockés en JSONB (`cms_document.data` pour la dernière version, `published_data` pour ce que voit le public). Les filtres `where` sont traduits en SQL sur ces colonnes.

## Installation

1. Mettre à jour le module : `docker exec odoo_web odoo -c /etc/odoo/odoo.conf -d odoo -u payload_cms --stop-after-init`, puis `docker compose restart web`.
2. Ouvrir **http://localhost:8069/admin**, ou *CMS → Admin Panel* dans Odoo. On se connecte avec un utilisateur Odoo membre du groupe *Payload CMS / Éditeur de contenu* ou *Administrateur*.
3. Configurer les collections dans *CMS → Configuration → Collections / Globals / Fields*.

> Avec plusieurs bases de données, configurez `dbfilter` (ou `db_name`) dans `odoo.conf`. Sinon, les appels `/api` anonymes d'un frontend ne savent pas quelle base utiliser.

## Recompiler les assets

```bash
# CSS : SCSS Payload + Tailwind CSS v4 → static/dist/admin.css
cd addons/payload_cms/static/admin_src && npm install && npm run build   # ou npm run watch

# Lexical : → static/lib/lexical/lexical.bundle.js
cd addons/payload_cms/static/lib/lexical && npm install && npm run build
```

Tailwind est branché sur les tokens de Payload (`bg-elevation-50`, `text-elevation-500`…) pour les éléments ajoutés propres à Odoo. Le rendu « à l'identique » vient des SCSS de Payload, importées dans la couche `payload-default`.

## API REST (compatible Payload)

| Méthode | Route | |
|---|---|---|
| GET | `/api/{collection}` | `where`, `sort`, `limit`, `page`, `depth`, `draft`, `pagination=false` |
| GET | `/api/{collection}/count` | `{ totalDocs }` |
| GET / PATCH / DELETE | `/api/{collection}/{id}` | `?draft=true` enregistre un brouillon, `?autosave=true` |
| POST | `/api/{collection}` | JSON, ou `multipart/form-data` (`file` + `_payload`) pour les uploads |
| PATCH / DELETE | `/api/{collection}?where[...]` | opérations groupées |
| POST | `/api/{collection}/{id}/duplicate` | |
| POST | `/api/{collection}/{id}/translate`, `/api/globals/{slug}/translate` | traduction automatique `{from, to, overwrite}` (`to` = code, liste ou `"all"`) |
| GET | `/api/{collection}/versions`, `/api/{collection}/versions/{id}` | |
| POST | `/api/{collection}/versions/{id}` | restaurer (`?draft=true` pour restaurer en brouillon) |
| GET / POST | `/api/globals/{slug}` (+ `/versions`) | |
| GET | `/api/{upload-collection}/file/{filename}` | fichiers et image sizes |
| POST | `/api/users/login`, `/api/users/logout`, `/api/users/refresh-token` ; GET `/api/users/me` | |

Opérateurs `where` : `equals`, `not_equals`, `in`, `not_in`, `all`, `like`, `not_like`, `contains`, `exists`, `greater_than(_equal)`, `less_than(_equal)`, combinables avec `and` / `or`. Les chemins imbriqués (`meta.title`) et les champs hasMany sont supportés.

Authentification :
- `Authorization: JWT <token>` (ou `Bearer`) ;
- `Authorization: users API-Key <clé>`, avec une clé API Odoo (Préférences → Sécurité du compte) ;
- le cookie de session Odoo.

### Format de sortie : REST pur

Les champs `richText` sont renvoyés en **HTML** (même rendu que `convertLexicalToHTML` de Payload), y compris dans les groupes, arrays, blocks et les réponses Live Preview :

```json
{ "id": 12, "title": "Accueil", "content": "<h2>Bienvenue</h2><p>Texte <strong>gras</strong></p>" }
```

- En écriture, un champ `richText` accepte du HTML (converti en état Lexical) ou un état Lexical JSON.
- `?richText=lexical` renvoie l'état Lexical brut (c'est ce que fait l'admin).

### Localisation

À activer dans **Configuration → Localization** (locales, locale par défaut, fallback, clé Google Translate), puis cochez **Localized** sur les champs concernés.

- `?locale=fr` : lecture et écriture dans cette locale ;
- `?locale=all` : toutes les valeurs `{ "en": …, "fr": … }` ;
- `?fallback-locale=none` : pas de repli sur la locale par défaut.

Les filtres `where` et les tris utilisent la locale demandée.

Traduction automatique, au choix dans **Configuration → Localization → Machine translation** :
- **MyMemory** : gratuit, sans clé. Quota de 5 000 caractères par jour, 50 000 avec un email.
- **Google Cloud Translation v2** : clé API.
- **LibreTranslate** : libre, auto-hébergeable (URL et clé optionnelle).

Pour les services qui limitent la taille des textes, le rich text est traduit bloc par bloc : chaque phrase garde son contexte, et titres, listes, gras et liens sont conservés. Les URL, emails et chemins ne sont jamais envoyés au traducteur. La case « Translate existing documents now » traduit d'un coup les documents déjà créés.

Déclenchement :
- action **Translate from …** dans le menu « … » du document ;
- ou `autoTranslate` : `missing` remplit les locales vides, `always` retraduit à chaque sauvegarde faite dans la locale par défaut.

Le texte est traduit en `text` ; le rich text passe par le HTML, ce qui conserve la mise en forme.

Pour qu'une collection change de contenu selon la langue, il faut que ses champs soient **Localized**. Deux façons de le faire :
- **Configuration → Localization → Translated collections** coche d'un coup les champs texte, textarea, rich text et slug de la collection. Retirer la collection ramène chaque valeur à la langue par défaut (migration automatique).
- La case **Localized**, champ par champ, dans Configuration → Collections.

Si aucun champ n'est localisé, un bandeau le signale dans l'écran d'édition. Avec `autoTranslate` activé, ouvrir un document dans une autre langue remplit automatiquement les traductions manquantes.

### Import / Export (CSV, Excel, JSON)

Dans chaque liste de l'admin, les boutons **Import** et **Export** sont à côté de « Create New ». Dans la barre de sélection, **Export** exporte uniquement les documents cochés.

- **Export** :
  - formats Excel (.xlsx), CSV (compatible Excel) ou JSON ;
  - tous les documents, la recherche en cours ou la sélection ;
  - choix des colonnes, et en-têtes en libellés ou en noms de champs.
- **Import** :
  - fichier CSV, .xlsx ou JSON, colonnes reconnues par nom ou par libellé (un export peut être réimporté) ;
  - modes *Create*, *Update* ou *Update or create*, avec rapprochement sur l'id, le slug ou un autre champ ;
  - **Validate** fait un essai à blanc qui liste les erreurs ligne par ligne sans rien écrire ;
  - chaque ligne est importée ou rejetée individuellement ;
  - des modèles vides (.xlsx / .csv) sont téléchargeables.
- **Format des cellules** :
  - groupes : `meta.title` ;
  - rich text : HTML ;
  - relations : ID (plusieurs : `1,2`) ;
  - arrays, blocks et JSON : texte JSON ;
  - booléens : `true`, `oui`, `x`… ;
  - nombres : `49,90` ou `49.90`.
- **API** :
  - `GET /api/{collection}/export?format=xlsx|csv|json&where=…&ids=…&fields=…` ;
  - `POST /api/{collection}/import` (multipart `file` + `_payload` : `{"mode","matchField","draft","dryRun","mapping"}`) ;
  - `GET /api/{collection}/import/template?format=xlsx`.

### Vues : Liste, Kanban, Pivot, Graphique, Calendrier

Chaque collection peut s'afficher sous cinq vues, avec des onglets en haut à droite de la liste, dans le style de Payload. Toutes partagent la recherche et les filtres de la liste, et chaque réglage est mémorisé par collection (`?view=kanban` dans l'URL).

- **Kanban** :
  - colonnes par statut, champ select/radio, case à cocher ou relation ;
  - glisser une carte vers une autre colonne modifie le document (publier, changer d'étape…) ;
  - les cartes montrent le titre, la vignette et les colonnes par défaut.
- **Pivot** :
  - lignes × colonnes sur n'importe quel champ groupable ; dates par jour, semaine, mois, trimestre ou année ;
  - mesures : nombre, somme, moyenne, minimum ou maximum d'un champ nombre ;
  - totaux, inversion des axes et export CSV.
- **Graphique** : barres (empilables), lignes ou camembert, avec les mêmes regroupements et mesures.
- **Calendrier** :
  - vue mensuelle sur une date (champ date, création ou modification) ;
  - glisser un document vers un autre jour change sa date.

Le pivot et le graphique sont calculés en SQL par `GET /api/{collection}/aggregate?groupBy=_status,createdAt:month&measures=count,sum:price&where=…`.

Le chatter Odoo (historique, messages, activités) reste accessible par « ⋯ → Open in Odoo ».

### Polices

Inter (texte) et Roboto Mono (code) sont chargées depuis Google Fonts. Ce sont les équivalents Google Fonts des polices système utilisées par Payload (SF Pro / SF Mono), qui restent en secours. Voir `static/admin_src/css/fonts.css`.

### Traduction d'un document

Le bouton **Translate** (icône 文A, à côté de Save) est visible dans toutes les langues. Il traduit la langue affichée vers la langue choisie, ou vers toutes les langues d'un coup, puis ouvre le résultat.

### Documentation Swagger / OpenAPI

Une spécification OpenAPI 3 est générée automatiquement à partir du schéma : champs, brouillons, versions, uploads, locales et sites.
- `/api-docs` : Swagger UI (servi par le module, sans CDN) ;
- `/api-docs/openapi.json` : la spécification (utilisable par Postman ou par un générateur de client, par exemple `openapi-typescript`) ;
- dans l'admin : **Developers → API Docs**.

Réglages dans **Configuration → API Docs Settings** :
- activation, et accès public ou réservé aux utilisateurs du CMS ;
- titre, version, description ;
- serveurs listés et collections documentées ;
- documentation des routes d'authentification.

### Multisite (multi-tenant, façon WordPress Multisite)

Activation : **Configuration → Multisite**. Cela crée deux collections :
- **Networks** : un domaine de base par réseau, par exemple `example.com` ;
- **Sites** (`tenants`) : chaque site a un sous-domaine (`blog` → `blog.example.com`) et, si besoin, des domaines personnalisés (« domain mapping »).

Pour chaque collection ou global marqué **Scoped per site** :
- un champ **Site** est ajouté automatiquement ;
- l'API ne renvoie que les documents du site courant, et les slugs sont uniques par site ;
- un global a un document par site, avec repli sur la version commune.

Le site courant est déterminé, dans cet ordre, par :
1. l'en-tête `X-Payload-Tenant: <id|slug>` ou le paramètre `?tenant=<id|slug>` (une valeur vide ou `all` signifie tous les sites) ;
2. le nom de domaine de la requête (`blog.example.com`, `www.ma-boutique.com`). Un frontend servi sur le domaine du site n'a donc rien à envoyer.

Dans l'admin, le sélecteur **Site** de la navigation filtre les listes et pré-remplit le site des nouveaux documents.

Côté utilisateurs :
- le champ **Sites** d'un utilisateur limite un éditeur à ces sites ;
- les administrateurs du CMS gèrent tous les sites.

Déploiement :
- créez un DNS wildcard `*.example.com` vers le serveur Odoo (reverse proxy avec `proxy_mode = True`) ;
- vérifiez que `dbfilter` ne dépend pas du sous-domaine (une seule base, ou `dbfilter = ^nom_de_la_base$`) ;
- les domaines des sites sont acceptés automatiquement en CORS (option « Allow site domains »).

### Form Builder (port de `@payloadcms/plugin-form-builder`)

Collections `forms` et `form-submissions` (groupe « Form Builder »).

Pour soumettre un formulaire, sans authentification :

```bash
curl -X POST http://localhost:8069/api/form-submissions -H 'Content-Type: application/json' \
  -d '{"form": 5, "submissionData": [{"field": "email", "value": "jane@example.com"}]}'
```

- Les champs requis et les emails sont validés selon le formulaire (erreurs Payload `ValidationError`).
- Les emails configurés sont ensuite mis en file d'attente dans `mail.mail`. Ils supportent `{{champ}}`, `{{*}}` et `{{*:table}}`.
- Le champ `emails` (destinataires) n'est jamais exposé aux clients anonymes (option de champ `private`).
- Une collection peut accepter les créations anonymes avec l'option **Public create** (`publicCreate`).

Les visiteurs anonymes ne voient que les documents **publiés** des collections `public_read`.

Paramètres système :
- `payload_cms.cors` : origines autorisées, séparées par des virgules. `*` autorise toutes les origines, mais sans cookies.
- `payload_cms.token_expiration` : durée de validité des JWT, en secondes (7200 par défaut).

### Exemple : frontend Next.js avec Live Preview

```ts
// collection "pages" → Live Preview URL : http://localhost:3000/{slug}
const res = await fetch('http://localhost:8069/api/pages?where[slug][equals]=accueil&depth=2')
const { docs } = await res.json()

// app/[slug]/LivePreview.tsx
'use client'
import { useLivePreview } from '@payloadcms/live-preview-react'
const { data } = useLivePreview({ initialData, serverURL: 'http://localhost:8069', depth: 2 })
```

Dans ce cas, ajoutez l'origine du frontend (par ex. `http://localhost:3000`) à `payload_cms.cors`.

## Définir des collections en code (comme un modèle Odoo)

`payload_cms` est une brique livrable : il n'a pas de menu. Un module qui en dépend déclare ses collections comme des modèles Odoo, et ajoute ses propres menus avec les actions `payload_cms.action_payload_*`. Voir `palais_lome` pour un exemple complet.

```python
# mon_module/models/atelier.py   (importé dans models/__init__.py)
from odoo.addons.payload_cms.payload import Collection, Global, fields

class Atelier(Collection):
    _name = 'ateliers'                 # slug : /api/ateliers, /admin/collections/ateliers
    _label = 'Atelier'                 # singulier (_label_plural : pluriel)
    _description = "Ateliers et expositions"
    _rec_name = 'title'                # titre dans l'admin (useAsTitle)
    _order = '-date_begin'             # tri par défaut
    _columns = ['title', 'date_begin', '_status']
    _drafts = True                     # brouillon / publié + versions
    _autosave = True

    title = fields.Char("Titre", required=True, translate=True, tab="Contenu")
    description = fields.RichTextEditor("Description", translate=True, tab="Contenu")   # éditeur Lexical
    date_begin = fields.Datetime("Début", required=True, tab="Dates", row="dates")
    date_end = fields.Datetime("Fin", tab="Dates", row="dates")              # même row : côte à côte
    event_type = fields.Selection([('atelier', 'Atelier'), ('exposition', 'Exposition')], "Type",
                                  default='atelier', sidebar=True)
    cover = fields.Image("Couverture", tab="Médias")                          # upload -> media
    related = fields.Many2many('posts', "Articles liés", sidebar=True)
    parent = fields.Many2one('ateliers', "Programme parent", sidebar=True)
    venue = fields.Group("Lieu", fields={'city': fields.Char("Ville", default="Lomé")})
    credits = fields.Array("Crédits", row_label='name', fields={
        'role': fields.Char("Rôle", translate=True, row="c"),
        'name': fields.Char("Nom", row="c"),
    })
    slug = fields.Slug(source='title')

class Settings(Global):
    _name = 'settings'
    _label = "Réglages du site"
    phone = fields.Char("Téléphone")
```

**Types de champs** :

| Odoo-like | Champ Payload |
|---|---|
| `Char`, `Text`, `Email` | text, textarea, email |
| `RichTextEditor` (alias `Html`) | richText (Lexical ; HTML dans l'API) |
| `Integer`, `Float` | number |
| `Boolean` | checkbox |
| `Date`, `Datetime` | date |
| `Selection` (`multiple=True`, `widget='radio'`), `Radio` | select / radio |
| `Slug` | slug |
| `Many2one`, `Many2many` | relationship |
| `Image` / `File` | upload |
| `Group`, `Array` (alias `One2many`) | group, array |
| `Blocks` + `Block` | blocks |
| `Json`, `Code`, `Point` | json, code, point |

**Paramètres** :
- valeur et validation : `string` (1er argument, comme Odoo), `required`, `default`, `help`, `translate=True` (une valeur par langue), `readonly`, `unique`, `placeholder`, `private`, `min`, `max` ;
- affichage conditionnel : `condition={'field': 'kind', 'equals': 'expo'}` ;
- mise en page : `tab="…"` (onglet), `row="…"` (côte à côte), `width="50%"`, `sidebar=True`, `hidden=True`.

**Options de collection** :
- `_group` : groupe de navigation. Par défaut « Collections », à la suite de Pages, Posts, Media et Users.
- `_sequence` : position dans la navigation.
- `_upload` : collection de fichiers.
- `_public_read` et `_public_create` : accès anonyme en lecture et en création.
- `_multi_tenant` : collection par site (multisite).
- `_live_preview_url` et `_preview_url` : aperçus.
- `_hidden` : collection masquée dans la navigation.

**Synchronisation** : les classes des modules installés sont appliquées automatiquement à l'installation, à la mise à jour et au démarrage d'Odoo, uniquement si leur définition a changé (empreinte stockée dans `cms.collection.code_hash`). Le code fait foi : dans Configuration → Collections, les champs d'une collection définie en code sont en lecture seule (« Defined in module »).

## Crédits

L'interface reprend les styles, les icônes et les libellés de [Payload](https://github.com/payloadcms/payload) (MIT, © Payload CMS, Inc.), vendored dans `static/admin_src/payload-scss` et `static/src/admin/core/{icons,translations}.js`.
