# Stack Docker Compose : Odoo 18, PostgreSQL 16 & pgAdmin 4

Environnement Docker prêt à l'emploi pour développer et déployer **Odoo 18**, avec base de données **PostgreSQL 16** et interface d'administration **pgAdmin 4**.

---

## 📁 Structure du projet

```text
.
├── .env                      # Variables d'environnement actives
├── .env.example              # Modèle de variables d'environnement
├── .gitignore                # Exclusion des fichiers sensibles et temporaires
├── docker-compose.yml        # Orchestration des conteneurs
├── README.md                 # Guide d'utilisation
├── addons/                   # Modules Odoo personnalisés (monté dans /mnt/extra-addons)
└── config/
    ├── odoo.conf             # Fichier de configuration d'Odoo
    └── pgadmin/
        └── servers.json      # Préconfiguration de connexion PostgreSQL pour pgAdmin
```

---

## 🚀 Démarrage rapide

### 1. Vérification des variables d'environnement
Un fichier `.env` a été généré à la racine. Vous pouvez ajuster les ports et mots de passe si souhaité.

### 2. Lancer les conteneurs
Exécutez la commande suivante à la racine du projet :
```bash
docker compose up -d
```

### 3. Vérifier le statut des services
```bash
docker compose ps
```

---

## 🌐 Accès aux interfaces web

| Service | URL locale | Identifiant par défaut | Mot de passe par défaut |
| :--- | :--- | :--- | :--- |
| **Odoo 18** | [http://localhost:8069](http://localhost:8069) | *À définir à la création de la base* | Master Password : `admin_super_secret_passwd` |
| **pgAdmin 4** | [http://localhost:5050](http://localhost:5050) | `admin@admin.com` | `admin_secure_password_123` |

> [!NOTE]
> Dans pgAdmin 4, la connexion au serveur PostgreSQL nommé **"Odoo PostgreSQL DB"** est pré-configurée automatiquement. Lors du premier clic sur ce serveur, entrez le mot de passe PostgreSQL (`odoo_secure_password_123`).

---

## 🧩 Ajout de modules personnalisés (Addons)

1. Déposez vos dossiers de modules dans le répertoire local `./addons/`.
2. Redémarrez le conteneur Odoo si nécessaire :
   ```bash
   docker compose restart web
   ```
3. Dans l'interface web d'Odoo :
   - Activez le **Mode Développeur** (dans Paramètres).
   - Rendez-vous dans **Applications** > Menu **Mettre à jour la liste des applications**.
   - Recherchez et installez votre module.

---

## 🛠️ Commandes utiles

- **Afficher les logs en temps réel :**
  ```bash
  docker compose logs -f
  # Ou uniquement pour Odoo :
  docker compose logs -f web
  ```

- **Arrêter la stack sans supprimer les données :**
  ```bash
  docker compose down
  ```

- **Redémarrer un service en particulier (ex: web) :**
  ```bash
  docker compose restart web
  ```

- **Arrêter la stack et supprimer tous les volumes (⚠️ Supprime toutes les données !) :**
  ```bash
  docker compose down -v
  ```
