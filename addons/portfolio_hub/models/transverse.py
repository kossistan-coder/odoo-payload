# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields


class HomepageStat(Collection):
    """Chiffres clés et statistiques pour la section Hero / Homepage."""
    _name = 'homepage-stats'
    _localized = True
    _sequence = 180
    _label = 'Statistique Homepage'
    _label_plural = 'Statistiques Homepage'
    _rec_name = 'label'
    _order = 'sequence, label'
    _columns = ['value', 'label', 'sequence', 'active']

    value = fields.Char("Valeur", required=True, localized=True, placeholder="ex: 12.000+, 100%", row="stat")
    label = fields.Char("Libellé", required=True, localized=True, placeholder="ex: Lignes de code, Taux de satisfaction", row="stat")
    sequence = fields.Integer("Ordre d'affichage", default=10, localized=True, sidebar=True)
    active = fields.Boolean("Actif", default=True, localized=True, sidebar=True, badge=("Actif", "Inactif"))


class NewsletterSubscriber(Collection):
    """Abonnés à la newsletter (création publique autorisée via l'API REST)."""
    _name = 'newsletter-subscribers'
    _localized = True
    _sequence = 190
    _label = 'Abonné Newsletter'
    _label_plural = 'Abonnés Newsletter'
    _rec_name = 'email'
    _order = '-subscribed_date'
    _columns = ['email', 'source', 'subscribed_date', 'active']
    _public_create = True    # Permet aux formulaires frontends de poster une inscription
    _public_read = False      # Les emails ne sont pas accessibles publiquement

    email = fields.Email("Adresse email", required=True, unique=True, localized=True)
    subscribed_date = fields.Datetime("Date d'inscription", localized=True, sidebar=True)
    source = fields.Selection([
        ('homepage', 'Page d\'accueil'),
        ('article', 'Article / Blog'),
        ('formation', 'Formation'),
        ('other', 'Autre'),
    ], "Source d'inscription", default='homepage', localized=True, sidebar=True, badge=True)
    active = fields.Boolean("Actif", default=True, localized=True, sidebar=True, badge=("Actif", "Inactif"))
