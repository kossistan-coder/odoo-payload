# -*- coding: utf-8 -*-
# from odoo import http


# class PalaisLome(http.Controller):
#     @http.route('/palais_lome/palais_lome', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/palais_lome/palais_lome/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('palais_lome.listing', {
#             'root': '/palais_lome/palais_lome',
#             'objects': http.request.env['palais_lome.palais_lome'].search([]),
#         })

#     @http.route('/palais_lome/palais_lome/objects/<model("palais_lome.palais_lome"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('palais_lome.object', {
#             'object': obj
#         })

