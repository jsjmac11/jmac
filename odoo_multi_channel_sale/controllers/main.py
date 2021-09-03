# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
import werkzeug
import base64

from odoo import http, SUPERUSER_ID
from odoo.http import request
from odoo.tools import image_process, image_guess_size_from_field_name
from odoo.addons.web.controllers.main import WebClient, Binary

import logging
_logger = logging.getLogger(__name__)

MAPPINGMODEL={
	'product.product':'channel.product.mappings',
	'sale.order':'channel.order.mappings',
	}
MAPPINGFIELD={
	'product.product':'erp_product_id',
	'sale.order':'odoo_order_id',
}

class Channel(http.Controller):
	@http.route(['/channel/update/mapping',],auth="public", type='json')
	def update_mapping(self, **post):
		field =MAPPINGFIELD.get(str(post.get('model')))
		model = MAPPINGMODEL.get(str(post.get('model')))
		if field and model:
			domain = [(field,'=',int(post.get('id')))]
			mappings=request.env[model].sudo().search(domain)
			for mapping in mappings:pass
				#mapping.need_sync='yes'
		return True

	def core_content_image(self, xmlid=None, model='ir.attachment', id=None, field='datas',
					  filename_field='datas_fname', unique=None, filename=None, mimetype=None,
					  download=None, width=0, height=0, crop=False, access_token=None, **kwargs):
		if not (width or height):
			width, height = image_guess_size_from_field_name(field)
		status, headers, content = request.env['ir.http'].sudo().binary_content(
            xmlid=xmlid, model=model, id=id, field=field, unique=unique, filename=filename,
            filename_field=filename_field, download=download, mimetype=mimetype, access_token=access_token)

		if status == 304:
			return werkzeug.wrappers.Response(status=304, headers=headers)
		elif status == 301:
			return werkzeug.utils.redirect(content, code=301)
		elif status != 200 and download:
			return request.not_found()

		if crop and (width or height):
			# default crop is fron center
			content = image_process(base64_source=content, size=(width or 0, height or 0), crop=crop)
		elif content and (width or height):
			# resize maximum 500*500
			if width > 500:
				width = 500
			if height > 500:
				height = 500
			content = image_process(base64_source=content, size=(width or 0, height or 0))
			# resize force jpg as filetype

		if not content:
			status = 200
			content = base64.b64encode(Binary().placeholder())

		content = base64.b64decode(content)

		headers = http.set_safe_image_headers(headers, content)
		response = request.make_response(content, headers)
		response.status_code = status
		return response

	@http.route([
	'/channel/image.png',
	'/channel/image/<xmlid>.png',
	'/channel/image/<xmlid>/<int:width>x<int:height>.png',
	'/channel/image/<xmlid>/<field>.png',
	'/channel/image/<xmlid>/<field>/<int:width>x<int:height>.png',
	'/channel/image/<model>/<id>/<field>.png',
	'/channel/image/<model>/<id>/<field>/<int:width>x<int:height>.png',
	'/channel/image/<model>/<id>/<field>/<string:alias_name>.png',
	'/channel/image/<model>/<id>/<field>/<int:width>x<int:height>/<string:alias_name>.png',
	'/channel/image.jpg',
	'/channel/image/<xmlid>.jpg',
	'/channel/image/<xmlid>/<int:width>x<int:height>.jpg',
	'/channel/image/<xmlid>/<field>.jpg',
	'/channel/image/<xmlid>/<field>/<int:width>x<int:height>.jpg',
	'/channel/image/<model>/<id>/<field>.jpg',
	'/channel/image/<model>/<id>/<field>/<int:width>x<int:height>.jpg',
	'/channel/image/<model>/<id>/<field>/<string:alias_name>.jpg',
	'/channel/image/<model>/<id>/<field>/<int:width>x<int:height>/<string:alias_name>.jpg',
	], type='http', auth="public", website=False, multilang=False)
	def content_image(self, id=None, **kw):
		if id:
			id, _, unique = id.partition('_')
			kw['id'] = int(id)
			if unique:
				kw['unique'] = unique
		return self.core_content_image(**kw)
