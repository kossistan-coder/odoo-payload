# Payload CMS pour Odoo (`payload_cms`)

Un CMS headless dans Odoo 18 qui reproduit [Payload CMS](https://payloadcms.com) (v3.90) :

- **Admin sur `/admin`** avec la même interface que Payload (thème clair) : dashboard, navigation, vues liste, édition, versions, API, compte et login. L'UI utilise les **feuilles SCSS originales de Payload** (licence MIT), compilées telles quelles. Les classes CSS et la structure HTML sont celles de Payload, ce qui donne le même rendu.
- **API « à la Odoo »** (`Model`, JSON-RPC, routes des modules documentées dans Swagger). L'API REST au format Payload sur `/api` est réservée à l'admin.
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

## API « à la Odoo » (édition : modules, admin, écritures)

Les collections se lisent et s'écrivent comme des modèles Odoo, avec des réponses simples. L'API REST `/api` reste l'API interne de l'admin, fermée au public.

**Formes des valeurs** (comme `read` dans Odoo) : une valeur vide vaut `false`. Une relation vaut `[id, "nom affiché"]` et une relation multiple une liste d'ids. Une image ou un fichier vaut son URL, un texte riche du HTML. Une date vaut `"2026-10-12"`, une date avec heure `"2026-10-12 18:00:00"` (UTC).

**En Python** (contrôleurs, seeders, crons…) :

```python
from odoo.addons.payload_cms.payload import Model

Events = Model(request.env, 'events')
Events.search_read([('active', '=', True)], ['designation', 'date_sortie', 'episode'], order='date_sortie desc', limit=3)
Events.web_search_read([('active', '=', True)], {           # champs choisis, relations imbriquées
    'designation': {}, 'couverture': {},
    'speakers': {'fields': {'nom': {}, 'prenom': {}, 'profile': {}}},
}, limit=3)                                                  # -> {'length': 7, 'records': [...]}
Events.create({'designation': 'Live', 'date_sortie': '2026-11-02', 'time': '18:00', 'speakers': [(6, 0, [38])]})
Events.write([68], {'speakers': [(4, 32)], 'active': False})
Events.unlink([68])
Events.fields_get(attributes=['type', 'relation'])
```

Méthodes : `search`, `search_count`, `search_read`, `read`, `web_search_read`, `web_read`, `name_search`, `fields_get`, `create`, `write`, `unlink`.
- Les domaines Odoo sont acceptés : `&`, `|`, `!`, `=`, `!=`, `in`, `not in`, `ilike`, `like`, `>`, `>=`, `<`, `<=`. `display_name`, `create_date` et `write_date` sont utilisables dans les domaines comme dans `order`.
- En écriture, les relations multiples acceptent les commandes x2many `(6, 0, ids)`, `(4, id)`, `(3, id)` et `(5,)`, ou une simple liste d'ids.
- Droits : un visiteur lit les documents publiés des collections en *Public read*, sans les champs privés. Les éditeurs CMS lisent et écrivent tout. `Model(...).sudo()` ignore les droits.
- Contexte : `Model(...).with_context(draft=True)` lit les brouillons (éditeurs uniquement), `with_context(lang='fr_FR')` choisit la langue.

**Vos propres méthodes d'API** : déclarez-les dans la classe de la collection avec `@expose`. `self` est le `Model` de la collection :

```python
from odoo.addons.payload_cms.payload import Collection, expose, fields

class Event(Collection):
    _name = 'events'
    ...
    @expose(auth='public')          # 'public' : tout le monde ; 'user' (défaut) : éditeurs CMS
    def replays(self, limit=None):
        return self.search_read([('episode', '!=', False)], ['designation', 'episode'], order='date_sortie desc', limit=limit)
```

**En JSON-RPC** (comme `/web/dataset/call_kw` d'Odoo), pour toutes ces méthodes, y compris les `@expose` :

```bash
curl -X POST https://site/payload/dataset/call_kw -H 'Content-Type: application/json' -d '{
  "jsonrpc": "2.0", "method": "call",
  "params": {"model": "events", "method": "search_read",
             "args": [[["active", "=", true]]],
             "kwargs": {"fields": ["designation", "date_sortie"], "order": "date_sortie desc", "limit": 3}}}'
```

Authentification : cookie de session Odoo, ou en-tête `Authorization: Bearer <clé API Odoo | JWT Payload>`. Sans en-tête, l'appel est anonyme.

**Vos propres routes** : un contrôleur Odoo classique qui utilise `Model` (exemple : `techlives_series/controllers/controllers.py`, `GET /techlives/api/lives`).

## API Delivery (contenu pour les frontends)

Deux API, deux usages :
- **édition / CMS** : `Model` et le JSON-RPC (forme des enregistrements Odoo), pour l'admin, les modules et les écritures ;
- **Delivery** : lecture seule, pour les sites et applications (Angular, Next.js, Flutter…). Le format est générique, simple et multilingue.

```python
from odoo.addons.payload_cms.payload import Delivery

Delivery(request.env, depth=2).document('pages', 'home')            # la page, relations peuplées (par slug ou id)
Delivery(request.env, locale='fr', depth=1).documents('events', [('active', '=', True)], order='date_sortie desc', limit=10)
```

```json
{
  "data": {
    "id": 1, "type": "page",
    "attributes": {"title": {"fr": "Accueil", "en": null}, "slug": {"fr": "home", "en": null}},
    "seo": {"title": {"fr": "Tech Lives Series", "en": null}, "description": {"fr": null, "en": null}, "image": null},
    "blocks": [
      {"id": "abc", "type": "episodesList",
       "config": {"mode": "auto", "limit": 3, "anchor": "episodes",
                  "source": {"collection": "event", "filter": [["active", "=", true]], "sort": "releaseDate desc", "limit": 3}},
       "content": {"title": {"fr": "Nos épisodes", "en": null}, "image": "https://cms.example.com/api/media/file/cover.jpg",
                   "events": [{"id": 68, "type": "event",
                               "attributes": {"title": {"fr": "Épisode 7 — …", "en": null}, "releaseDate": "2026-10-12",
                                              "cover": "https://cms.example.com/api/media/file/vignette.jpg",
                                              "speakers": [{"id": 38, "type": "speaker",
                                                            "attributes": {"firstName": "Yao", "lastName": "BATAKA", "profile": "https://…",
                                                                           "events": [{"id": 68, "type": "event", "displayName": "Épisode 7 — …"}]}}]}}]}}
    ],
    "meta": {"locale": "all", "availableLocales": ["fr", "en"], "status": "published", "publishedAt": null,
             "createdAt": "2026-09-23T23:20:02Z", "updatedAt": "2026-09-24T09:48:32Z"}
  },
  "meta": {"locale": "all", "availableLocales": ["fr", "en"], "defaultLocale": "fr", "depth": 2}
}
```

Règles :
- **Relations peuplées** : une relation vaut les documents liés eux-mêmes, avec toutes leurs informations, directement à leur place (`events`, `speakers`, `live`…), jusqu'à `depth` niveaux (maximum 3). Au-delà, et avec `depth=0`, un document lié est résumé en `{id, type, displayName}`, ce qui coupe les boucles comme live → intervenant → live. Il n'y a jamais d'ids seuls, et aucune clé n'est un nombre.
- **Fichiers** : une image ou un fichier vaut son **URL absolue**.
- **Structure** : `id` et `type`, puis `attributes`, `seo` (le groupe `meta` / `seo`), `blocks` (le champ blocks de la collection) et `meta` (statut, dates, langues ; seulement au premier niveau). Une liste renvoie `data: [...]` et, dans `meta`, `total`, `limit` et `offset`.
- **Nommage** : les clés sont en `camelCase` et les types au singulier en `camelCase` (`pages` → `page`, bloc `live-hero` → `liveHero`). `api_name=` renomme un champ sans migrer les données, par exemple `designation = fields.Char("Désignation", api_name="title")`.
- **Valeurs absentes** : `null`, et `[]` pour une liste.
- **Collections non lisibles** : les relations vers une collection que le lecteur ne peut pas lire (par exemple les participants) ne sont pas exposées.
- **Langues** : un champ traduisible vaut toujours `{langue: valeur}`. Avec `locale='all'`, toutes les langues disponibles sont présentes, avec `null` si la valeur n'est pas traduite. Avec `locale='fr'`, seule la langue demandée est présente, et la langue par défaut sert de repli.
- **Blocs** : `{id, type, config, content}`. Les champs select, radio, checkbox et number vont dans `config`, les autres dans `content`. `role='config'` ou `role='content'` sur un champ change ce choix.
- **Blocs automatiques** : un bloc code-first décrit les enregistrements qu'il affiche avec `_delivery_sources`. La requête apparaît dans `config.source` (`collection`, `filter`, `sort`, `limit`, avec les noms de l'API) et les documents trouvés dans `content`.

  ```python
  class EpisodesList(Block):
      _name = 'episodes-list'
      ...
      @classmethod
      def _delivery_sources(cls, row, env):
          if row.get('mode') == 'manual':
              return []            # sélection manuelle : les documents choisis dans l'admin
          return [{'field': 'events', 'collection': 'events', 'domain': [('active', '=', True)],
                   'order': 'date_sortie desc', 'limit': int(row.get('limit') or 3)}]
  ```

- **Documentation** : `@api_doc(delivery=True, depth=1, model='events')` décrit ce format dans Swagger, avec les relations populées par défaut par la route.
- **Exemple** : `techlives_series/controllers/controllers.py`.
  - `GET /techlives/api/pages/<slug|id>` renvoie la page complète (`depth=2`).
  - `/lives` et `/intervenants` utilisent `depth=1`, `/lives/<slug>` utilise `depth=2`, `/pages` utilise `depth=0`.
  - Paramètres : `?locale=all|fr|en`, `?depth=`, `?draft=1` (utilisateurs du CMS).

## API REST interne (`/api`, format Payload)

`/api` est l'API interne de l'admin : elle est réservée aux utilisateurs du CMS (session, JWT ou clé API d'un éditeur). Seuls les fichiers des collections upload (`/api/<collection>/file/<nom>`, les images du site) et le login restent publics. L'API publique d'un site s'écrit dans son module (voir « API à la Odoo » ci-dessus).

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

### Thème clair / sombre

Comme dans Payload : **Account → Admin Theme** (Automatic / Light / Dark), ou l'icône soleil / lune en bas de la navigation. « Automatic » suit le thème du système (`prefers-color-scheme`) en direct. Le choix est mémorisé par navigateur (localStorage + cookie `payload-theme`) et appliqué avant le premier affichage (pas de flash). Il vaut aussi pour la page Swagger (`/api-docs`, `?theme=dark|light` pour forcer) et pour l'admin intégré dans Odoo. Code : `static/src/admin/core/theme.js`.

### Traduction d'un document

Le bouton **Translate** (icône 文A, à côté de Save) est visible dans toutes les langues. Il traduit la langue affichée vers la langue choisie, ou vers toutes les langues d'un coup, puis ouvre le résultat.

### Documentation Swagger / OpenAPI

La documentation décrit **l'API écrite par vos modules**, et non les routes internes de payload_cms. Elle contient :
- **toutes les routes des contrôleurs** de vos modules (chaque fichier `controllers/*.py` importé dans `controllers/__init__.py`). `@api_doc` les complète (paramètres, corps, schéma de la réponse) ou en masque une avec `@api_doc(hidden=True)` ;
- les méthodes de vos collections marquées `@expose` ;
- l'endpoint JSON-RPC générique `/payload/dataset/call_kw`, et le login (optionnels).

```python
from odoo.addons.payload_cms.payload import Model, api_doc

@api_doc(tags=['Lives'], params={'limit': (int, "Nombre maximum")}, model='events', fields=CARD, paginated=True)
@http.route('/techlives/api/lives', type='http', auth='public', methods=['GET'])
def lives(self, limit=None):
    """Lives actifs, du plus récent au plus ancien."""   # -> résumé et description
    ...
```

- Chemin, méthodes, paramètres d'URL (`<string:slug>`) et authentification (`auth='public'` ou `'user'`) viennent de `@http.route`.
- Le **schéma de la réponse** est généré à partir de la collection (`model`) et des champs renvoyés (`fields` : une liste pour la forme `read`, une spécification pour la forme `web_read` avec relations imbriquées). `many=True` indique une liste, `paginated=True` une réponse `{length, records}`, et `response=` accepte un schéma OpenAPI libre.
- `body=[...]` décrit le corps JSON d'une route POST à partir des champs de `model`. `params` décrit les paramètres de requête, ou les `params` JSON-RPC pour une route `type='json'`.
- `@expose(auth='public', model='events', fields=CARD, many=True)` documente une méthode de collection, appelable sur `POST /payload/dataset/call_kw/events/<méthode>`. Ses paramètres sont déduits de sa signature.

Accès :
- `/api-docs` : Swagger UI (servi par le module, sans CDN) ;
- `/api-docs/openapi.json` : la spécification ;
- dans l'admin : **Developers → API Docs**.

Réglages dans **Configuration → API Docs Settings** : activation, accès public, titre, version, description, serveurs, **modules documentés** (vide = tous les modules qui utilisent payload_cms), endpoint JSON-RPC générique et login.

**Onglet API d'un document** : il montre le document tel que votre API le lit (`web_read`, forme Odoo). La spécification des champs est modifiable pour préparer celle d'un contrôleur, et des boutons copient l'appel en curl ou en Python. L'onglet liste aussi les routes documentées de la collection.

### Blocs réutilisables (Configuration → Blocks)

Des blocs de mise en page créés sans code, pour composer les sections des pages. Un bloc est un assemblage de composants élémentaires :

| Composant | Champ Payload généré |
|---|---|
| Text, Textarea, Email, Number, Checkbox, Date, Select | champ du même type |
| Rich Text Editor | `richText` (Lexical) |
| Button | groupe `{ label, url, appearance, newTab }` |
| Image | `upload` vers une collection média |
| Relationship | `relationship` |
| List | `array` dont chaque élément contient ses propres composants (cartes, boutons…) |

- **Available in** : champs `blocks` qui proposent le bloc (`pages.layout` par défaut).
- **Section header** : ajoute d'abord `title` (obligatoire), `subtitle` et `description`, comme `SectionBlock`.
- Le bloc est stocké dans `cms.block` et ajouté à la configuration des champs ciblés : API, validation et admin le traitent comme un bloc déclaré dans la collection (`blockType` = slug du bloc).
- Un bloc utilisé par des documents ne peut pas être supprimé (archivez-le). Renommer son slug détache les lignes déjà écrites.

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

### Stockage des fichiers (MinIO / S3)

Par défaut, les fichiers des collections d'upload (`media`…) et leurs tailles d'image sont stockés comme pièces jointes Odoo (`ir.attachment`, filestore). Ils peuvent aussi l'être dans un bucket compatible S3 (AWS S3, MinIO, Scaleway, Cloudflare R2…) : **Configuration → Storage** (ou menu Odoo *Configuration → Storage*).

- Le client S3 est intégré (`tools/storage.py`, signature AWS V4 avec `requests`) : aucune dépendance à installer.
- Chaque document retient son stockage (`storage`, `storage_key`, `sizes[*].key`) : après un changement de stockage, les anciens fichiers restent servis et seuls les nouveaux uploads vont dans le nouveau stockage. La case **Move existing files to this storage** copie les fichiers existants, puis supprime les originaux (après la copie, et après le commit pour les objets S3).
- La connexion est testée à l'enregistrement (écriture / lecture / suppression d'un objet) ; **Create the bucket if missing** crée le bucket.
- Livraison des fichiers : **Through Odoo** (défaut, bucket privé) — les URLs restent `/api/<collection>/file/<nom>` et Odoo relaie le contenu ; **Directly** — les URLs pointent vers l'URL publique (`Public base URL`, bucket public ou CDN) et `/api/<collection>/file/<nom>` redirige vers elle.
- La clé secrète n'est jamais renvoyée à l'admin (champ vide = clé conservée).

Les variables d'environnement (ou les options `payload_storage`, `payload_s3_*` d'`odoo.conf`) priment sur les réglages de l'admin, où elles apparaissent en lecture seule :

| Variable | Rôle |
|---|---|
| `PAYLOAD_STORAGE` | `native` ou `s3` |
| `PAYLOAD_S3_ENDPOINT` | ex. `http://minio:9000` (vide = AWS S3) |
| `PAYLOAD_S3_REGION` | ex. `us-east-1` |
| `PAYLOAD_S3_BUCKET` | nom du bucket |
| `PAYLOAD_S3_ACCESS_KEY` / `PAYLOAD_S3_SECRET_KEY` | identifiants |
| `PAYLOAD_S3_PREFIX` | dossier des objets dans le bucket (optionnel) |
| `PAYLOAD_S3_ADDRESSING` | `path` (MinIO) ou `virtual` |
| `PAYLOAD_S3_PUBLIC_URL` | ex. `http://localhost:9010/payload-media` ou un CDN |
| `PAYLOAD_S3_DELIVERY` | `proxy` (défaut) ou `public` |

Avec docker compose, le service `minio` (profil `minio`, ports 9010 / console 9011) et le service ponctuel `createbuckets` sont optionnels :

```bash
docker compose up -d minio createbuckets   # MINIO_PUBLIC_BUCKET=true rend le bucket lisible anonymement
```

puis, dans `.env` (et `docker compose up -d web` pour appliquer) :

```dotenv
PAYLOAD_STORAGE=s3
PAYLOAD_S3_ENDPOINT=http://minio:9000
PAYLOAD_S3_BUCKET=payload-media
PAYLOAD_S3_ACCESS_KEY=minioadmin
PAYLOAD_S3_SECRET_KEY=minio_secure_password_123
PAYLOAD_S3_ADDRESSING=path
# livraison directe (bucket public) :
# PAYLOAD_S3_PUBLIC_URL=http://localhost:9010/payload-media
# PAYLOAD_S3_DELIVERY=public
```

Sans ces variables, le stockage natif reste utilisé (ou celui choisi dans l'admin).

### Form Builder (port de `@payloadcms/plugin-form-builder`)

Collections `forms` et `form-submissions` (groupe « Form Builder »).

Pour soumettre un formulaire, sans authentification (JSON-RPC, ou une route de votre module qui appelle `Model(env, 'form-submissions').create(...)`) :

```bash
curl -X POST http://localhost:8069/payload/dataset/call_kw -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "call", "params": {"model": "form-submissions", "method": "create",
       "args": [{"form": 5, "submissionData": [{"field": "email", "value": "jane@example.com"}]}]}}'
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

**Blocs de mise en page (pages personnalisées)** : les pages sont des documents de la collection native **Pages** (y compris l'accueil, slug `home`). Leur champ `layout` se compose de blocs : Content, Media, Call to Action et Archive par défaut. Un module y ajoute ses propres blocs, qui apparaissent dans « Add Layout » :

```python
from odoo.addons.payload_cms.payload import Block, fields

class LiveHero(Block):
    _name = 'live-hero'              # blockType dans l'API
    _label = 'Hero live'
    _inherit = 'pages.layout'        # '<collection>.<champ blocks>', ou une liste de cibles
    _sequence = 10                   # ordre dans « Add Layout »

    live = fields.Many2one('events', "Live mis en avant")
    badge = fields.Char("Badge", translate=True)
    cta_label = fields.Char("Bouton", default="Regarder l'épisode", row="cta")
    cta_url = fields.Char("Lien", row="cta")
```

- **Synchronisation** : comme les collections, le bloc est ajouté ou mis à jour à l'installation et à la mise à jour du module, et retiré si sa classe disparaît.
- **Préservation** : le reste de la collection n'est pas touché (traductions, modifications faites dans le constructeur).
- **API** : un bloc apparaît dans `layout` avec son `blockType`, par exemple `{"blockType": "live-hero", "live": 12, "badge": "…"}`.

**Bloc par défaut « Section »** : `payload_cms` ajoute au layout des Pages un bloc `section`, disponible quel que soit le module :

```ts
type SectionBlock = {
  blockType: 'section'
  title: LocalizedString        // obligatoire
  subtitle?: LocalizedString    // facultatif
  description: LocalizedString  // obligatoire
}
```

`SectionBlock` sert aussi de base aux blocs d'un module : `class MonBloc(SectionBlock)` reçoit d'abord ces trois champs, puis les siens (`from odoo.addons.payload_cms.payload import SectionBlock`).

**Seeders (contenu de démarrage)** : ils sont séparés des modèles, dans un dossier `seeders/` du module (importé par son `__init__.py`).

```python
# mon_module/seeders/home_page.py
from odoo.addons.payload_cms.payload import Seeder

class HomePage(Seeder):
    _name = 'home_page'
    _description = "Page d'accueil"

    def run(self, env):
        if self.exists(env, 'pages', {'slug': {'equals': 'home'}}):
            return
        self.create(env, 'pages', {'title': 'Accueil', 'slug': 'home', 'layout': [...]})
```

- **Exécution** : chaque seeder s'exécute **une seule fois par base**, après la synchronisation des collections et des blocs. L'exécution est mémorisée dans le paramètre système `payload_cms.seeder.<module>.<nom>`. Pour relancer : `env['cms.collection']._payload_run_seeders(force=True, names=['mon_module.home_page'])`.
- **Uniquement créer ou mettre à jour** : pendant un seeder, toute suppression de document, version, collection ou champ du CMS lève une erreur, et le seeder est annulé entièrement. Un seeder ne peut donc ni vider ni casser la base.
- **Robustesse** : un seeder en erreur est journalisé sans bloquer le démarrage d'Odoo.
- **Utilitaires** : `exists(env, slug, where)`, `create(env, slug, data, publish=True)`, `upsert(env, slug, where, data)` (met à jour ou crée) et `update_global(env, slug, data)`.

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
- mise en page : `tab="…"` (onglet), `row="…"` (côte à côte), `width="50%"`, `sidebar=True`, `hidden=True` ;
- badges colorés dans les vues liste et kanban (comme le widget `badge` d'Odoo) :

  ```python
  active = fields.Boolean("Actif", badge=("Actif", "Inactif"))                    # vert / rouge
  hidden = fields.Boolean("Masqué", badge={True: ("Masqué", "muted"), False: ("Visible", "success")})
  status = fields.Selection([('new', 'Nouveau', 'info'), ('done', 'Traité', 'success')], "Statut")  # 3e élément = couleur
  kind = fields.Selection(KINDS, "Type", badge=True)                               # couleurs attribuées tour à tour
  ```

  Couleurs : `success` (vert), `danger` (rouge), `warning` (orange), `info` (bleu), `primary` (violet), `muted` (gris), ou une couleur CSS (`"#0ea5e9"`). Sans code : liste **Badges** des champs checkbox, select et radio dans Configuration → Collections.

**Options de collection** :
- `_group` : groupe de navigation. Par défaut « Collections », à la suite de Pages, Posts, Media et Users.
- `_sequence` : position dans la navigation.
- `_upload` : collection de fichiers.
- `_public_read` et `_public_create` : accès anonyme en lecture et en création.
- `_multi_tenant` : collection par site (multisite).
- `_live_preview_url` et `_preview_url` : aperçus.
- `_hidden` : collection masquée dans la navigation.

**Synchronisation** : les classes des modules installés sont appliquées automatiquement à l'installation, à la mise à jour et au démarrage d'Odoo, uniquement si leur définition a changé (empreinte stockée dans `cms.collection.code_hash`). Le code fait foi : dans Configuration → Collections, les champs d'une collection définie en code sont en lecture seule (« Defined in module »).

## Étendre l'admin OdooPayload depuis un module (vues, widgets, champs)

Un module qui dépend de `payload_cms` peut ajouter ses propres écrans à l'admin, qui s'affichent avec l'interface OdooPayload (thème clair / sombre compris). Les vues XML Odoo (`ir.ui.view`) restent, elles, affichées par le client web Odoo natif.

| Besoin | Ce qu'on écrit | Rendu |
|---|---|---|
| Contenu géré par des éditeurs | une classe `Collection` (Python) | liste, édition, kanban… générés automatiquement |
| Écran sur mesure dans l'admin (statistiques, tableau de bord…) | `registerView(...)` (JS, OWL) | page `/admin/x/<chemin>`, dans la navigation |
| Encart sur le tableau de bord | `registerDashboardWidget(...)` | au-dessus des collections |
| Saisie spéciale pour un champ (couleur, carte…) | `registerField(...)` + `component="..."` sur le champ | remplace la saisie par défaut |
| Données métier Odoo | modèle Odoo + vues XML | interface native Odoo |

**1. Déclarer les fichiers** dans le manifest du module (ils rejoignent le bundle de l'admin) :

```python
'assets': {
    'payload_cms.assets_admin': [
        'mon_module/static/src/payload/**/*',     # .js, .xml (templates OWL), .css
    ],
},
```

**2. Enregistrer les écrans** (`mon_module/static/src/payload/stats.js`) :

```javascript
/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { callKw, registerDashboardWidget, registerField, registerView } from "@payload_cms/admin/core/extensions";
import { setStepNav } from "@payload_cms/admin/core/store";

class StatsView extends Component {
    static template = "mon_module.StatsView";        // défini dans un .xml du même dossier
    setup() {
        this.state = useState({ lives: 0 });
        onWillStart(async () => {
            setStepNav([{ label: "Statistiques" }]);   // fil d'Ariane (sinon : le libellé de la vue)
            this.state.lives = await callKw("events", "search_count", [[["active", "=", true]]]);
        });
    }
}

registerView({ path: "statistiques", label: "Statistiques", group: "Mon site", component: StatsView });
registerDashboardWidget({ key: "prochain-live", component: NextLiveWidget, width: "half" });
```

- `registerView({path, label, component, group, sequence, adminOnly, nav, title})` : la vue répond sur `/admin/x/<path>` et sur ses sous-chemins (`props.route.params.subpath`, `props.route.query`). Elle apparaît dans la navigation et sur le tableau de bord (groupe `group`), sauf avec `nav: false`. `adminOnly: true` la réserve aux administrateurs du CMS.
- `registerDashboardWidget({key, component, width, sequence, adminOnly})` : `width` vaut `"full"`, `"half"` ou `"third"`.
- `registerField(name, Component)` : le composant (qui étend `FieldBase` de `@payload_cms/admin/fields/field_base` : `this.value`, `this.setValue(v)`, `this.field`, `this.readOnly`) remplace la saisie des champs déclarés avec `component="<name>"` :

  ```python
  couleur = fields.Char("Couleur", component="color")
  ```

- `callKw(model, method, args, kwargs)` appelle l'API « à la Odoo » (`search_read`, `web_search_read`, `create`, méthodes `@expose`…), comme `orm.call` dans Odoo.
- Les autres modules de l'admin sont importables : `@payload_cms/admin/core/store` (`setStepNav`, `toast`, `store`), `@payload_cms/admin/components/base` (`Button`, `Pill`, `Select`…), `@payload_cms/admin/core/utils` (`icon`).
- Pour que le rendu suive le thème clair / sombre, utilisez les classes de Payload (`gutter`, `card`, `table`, `field-description`…) et ses variables CSS (`var(--theme-text)`, `var(--theme-elevation-500)`…).

**3. Ouvrir l'écran depuis un menu Odoo** :

```xml
<record id="action_stats" model="ir.actions.client">
    <field name="name">Statistiques</field>
    <field name="tag">payload_cms.admin</field>
    <field name="params" eval="{'path': '/x/statistiques'}"/>
</record>
<menuitem id="menu_stats" name="Statistiques" parent="menu_root" action="action_stats"/>
```

Exemple complet : `techlives_series/static/src/payload/` (vue « Statistiques » et widget « Prochain live ») et son menu dans `techlives_series/views/menus.xml`.

## Crédits

L'interface reprend les styles, les icônes et les libellés de [Payload](https://github.com/payloadcms/payload) (MIT, © Payload CMS, Inc.), vendored dans `static/admin_src/payload-scss` et `static/src/admin/core/{icons,translations}.js`.
