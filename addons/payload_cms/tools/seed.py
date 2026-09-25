# -*- coding: utf-8 -*-
"""Script CLI d'exécution des seeders Payload CMS en environnement de développement.

Utilisation avec Docker :
    docker compose run --rm web python3 -m odoo.addons.payload_cms.tools.seed [-d <db>] [--force] [--names <nom>]
"""
import argparse
import os
import sys


def main():
    import odoo

    odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])

    parser = argparse.ArgumentParser(description="Exécuter les seeders Payload CMS")
    parser.add_argument('-d', '--database', default=odoo.tools.config.get('db_name') or 'odoo', help="Nom de la base de données")
    parser.add_argument('--force', action='store_true', help="Forcer la ré-exécution des seeders déjà appliqués")
    parser.add_argument('--names', nargs='*', help="Liste de seeders spécifiques (ex: portfolio_hub.pages)")
    args = parser.parse_args()

    # Active l'autorisation des seeders pour cette session
    os.environ['PAYLOAD_RUN_SEEDERS'] = '1'
    if not os.environ.get('PAYLOAD_ENV'):
        os.environ['PAYLOAD_ENV'] = 'development'

    db = odoo.sql_db.db_connect(args.database)
    with db.cursor() as cr:
        env = odoo.api.Environment(cr, 1, {})
        print(f"\n[Payload CMS] Lancement des seeders sur la base '{args.database}'...")
        done = env['cms.collection']._payload_run_seeders(force=args.force, names=args.names)
        cr.commit()
        if done:
            print(f"[Payload CMS] Succès : {len(done)} seeder(s) exécuté(s) :")
            for name in done:
                print(f"  ✓ {name}")
        else:
            print("[Payload CMS] Aucun seeder à exécuter (tous déjà appliqués ou ignorés). Utilisez --force pour forcer la mise à jour.")


if __name__ == '__main__':
    main()
