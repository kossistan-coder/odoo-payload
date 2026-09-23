# Module Odoo : Payload CMS (`payload_cms`)

Ce module intègre dans le backend d'Odoo l'expérience d'administration de **Payload CMS** :
- **Collections déclaratives** (`cms.collection` et `cms.field.definition`)
- **Collection par défaut 'Pages'** (`cms.page`) avec cycle de publication (`draft`, `published`, `archived`)
- **Éditeur de texte riche Lexical (Vanilla)** intégré sous forme de widget OWL natif Odoo (`payload_lexical`)
- **Format de données sérialisé JSON** 100% compatible avec l'arbre de nœuds Lexical (`root.children[]`) de Payload CMS
- **Mise en page à deux colonnes** avec zone principale de contenu et sidebar latérale pour les statuts et métadonnées

---

## 🏗️ Architecture du module

```text
payload_cms/
├── __init__.py
├── __manifest__.py
├── README.md
├── security/
│   ├── payload_cms_security.xml        # Groupes d'accès (Éditeur de contenu & Administrateur CMS)
│   └── ir.model.access.csv             # Permissions CRUD
├── models/
│   ├── cms_collection.py               # Méta-modèle des collections
│   ├── cms_field_definition.py         # Définition des champs déclaratifs
│   ├── cms_page.py                     # Modèle concret des pages (collection par défaut)
│   └── cms_block.py                    # Blocs de contenu modulaires
├── views/
│   ├── cms_menus.xml                   # Menu principal 'CMS' et sous-menus
│   ├── cms_page_views.xml              # Vues liste, recherche et formulaire style Payload
│   ├── cms_collection_views.xml        # Configuration des collections
│   └── cms_field_definition_views.xml  # Configuration des champs
└── static/
    ├── lib/
    │   └── lexical/
    │       ├── package.json            # Dépendances Lexical vanilla
    │       ├── build.js                # Script de bundling autonome esbuild
    │       └── lexical.bundle.js       # Bundle JS autonome compilé (167 KB)
    └── src/
        ├── scss/
        │   ├── payload_cms.scss        # Layout formulaire 2 colonnes / sidebar Payload
        │   └── lexical_editor.scss     # Styles isolés sous .o_payload_cms_lexical
        ├── js/
        │   ├── lexical_editor/
        │   │   ├── lexical_theme.js    # Classes CSS du thème Lexical
        │   │   ├── lexical_helper.js   # Normalisation et sérialisation JSON compatible Payload
        │   │   └── lexical_features.js # Registre extensible des fonctionnalités (bold, h1-h3, listes...)
        │   └── widgets/
        │       └── lexical_field.js    # Composant OWL LexicalRichTextField
        └── xml/
            └── lexical_field.xml       # Template QWeb OWL de l'éditeur
```

---

## 📦 Compilation du bundle Lexical (Build NPM)

Le bundle `static/lib/lexical/lexical.bundle.js` est **déjà pré-compilé et prêt à l'emploi** dans ce dépôt.

Si vous souhaitez modifier les dépendances Lexical ou ajouter des extensions officielles Lexical, vous pouvez recompiler le bundle comme suit :

### Option A : Avec Node.js installé localement
```bash
cd addons/payload_cms/static/lib/lexical
npm install
npm run build
```

### Option B : Via Docker (sans installer Node.js sur votre machine)
```bash
docker run --rm -v $(pwd)/addons/payload_cms/static/lib/lexical:/app -w /app node:22-alpine sh -c "npm install && node build.js"
```

Le script utilise `esbuild` pour compiler Lexical Core, RichText, List, Link, History et Utils dans un fichier autonome au format IIFE exposant l'objet global `window.PayloadLexical`.

---

## 🚀 Installation et activation dans Odoo

1. **Redémarrer le conteneur Odoo** (pour prendre en compte les nouveaux fichiers Python et vues XML) :
   ```bash
   docker compose restart web
   ```

2. **Accéder à l'interface Odoo** :
   Ouvrez votre navigateur sur [http://localhost:8069](http://localhost:8069).

3. **Activer le module** :
   - Rendez-vous dans **Paramètres** et activez le **Mode Développeur**.
   - Rendez-vous dans le menu **Applications**.
   - Cliquez sur **Mettre à jour la liste des applications** (menu haut).
   - Supprimez le filtre *"Applications"* dans la barre de recherche.
   - Recherchez **Payload CMS** et cliquez sur **Activer**.

4. **Accès au CMS** :
   L'icône **CMS** apparaît désormais dans la barre d'applications Odoo de premier niveau avec les sections *Pages*, *Collections* et *Champs*.

---

## 🔮 Roadmap & Prochaines itérations

- [ ] **Système de Blocs Drag & Drop** : Réordonnancement interactif des blocs de contenu (`cms.block`) avec prévisualisation en direct dans la page.
- [ ] **Médiathèque avancée (Upload & Media Library)** : Gestionnaire de médias centralisé avec prévisualisation des images, recadrage et métadonnées focal point comme dans Payload.
- [ ] **Gestion des versions & Historique** : Système de drafts, révisions et publication planifiée.
- [ ] **Générateur dynamique de formulaires** : Rendu dynamique des formulaires Odoo basé sur les déclarations de `cms.field.definition`.
