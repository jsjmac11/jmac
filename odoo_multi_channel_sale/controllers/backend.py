# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import fields,http
from odoo.http import request


class WebsiteBackend(http.Controller):
	@http.route('/multichannel/fetch_dashboard_data',type='json',auth='user')
	def fetch_dashboard_data(self,obj,days,**kw):
		today = fields.date.today()
		labels = []
		request._cr.execute("""
			SELECT id,name,color
				FROM multi_channel_sale
				WHERE state != 'draft'
		""")
		data = request._cr.dictfetchall()

		if obj == 'order':
			request._cr.execute(f"""
				SELECT m.channel_id,to_char(o.date_order,'dd') as day,COUNT(o.id)
					FROM channel_order_mappings m
					LEFT JOIN sale_order o
						On m.odoo_order_id = o.id
					WHERE to_char(o.date_order,'MM-YYYY') = '{today.strftime('%m-%Y')}'
					GROUP BY 1,2
			""")
		elif obj == 'product':
			request._cr.execute(f"""
				SELECT m.channel_id,to_char(p.create_date,'dd') as day,COUNT(p.id)
					FROM channel_template_mappings m
					LEFT JOIN product_template p
						On m.template_name = p.id
					WHERE to_char(p.create_date,'MM-YYYY') = '{today.strftime('%m-%Y')}'
					GROUP BY 1,2
			""")
		elif obj == 'category':
			request._cr.execute(f"""
				SELECT m.channel_id,to_char(c.create_date,'dd') as day,COUNT(c.id)
					FROM channel_category_mappings m
					LEFT JOIN product_category c
						On m.odoo_category_id = c.id
					WHERE to_char(c.create_date,'MM-YYYY') = '{today.strftime('%m-%Y')}'
					GROUP BY 1,2
			""")
		elif obj == 'customer':
			request._cr.execute(f"""
				SELECT m.channel_id,to_char(c.create_date,'dd') as day,COUNT(c.id)
					FROM channel_partner_mappings m
					LEFT JOIN res_partner c
						On m.odoo_partner_id = c.id
					WHERE to_char(c.create_date,'MM-YYYY') = '{today.strftime('%m-%Y')}'
					GROUP BY 1,2
			""")

		counts = {}
		for obj in request._cr.dictfetchall():
			counts.setdefault(obj['channel_id'],{})[obj['day']] = obj['count']

		labels = []
		for i in range(days-1,-1,-1):
			date = fields.Datetime.subtract(today,days=i)
			for instance in data:
				instance.setdefault('count',[]).append(
					counts.get(instance['id'],{}).get(date.strftime('%d'),0)
				)
			if days == 7:
				labels.append(date.strftime('%A'))
			else:
				labels.append(date.strftime('%d'))

		instance_data = {}
		for instance in request.env['multi.channel.sale'].search([('state','!=','draft')]):
			instance_data[instance.name] = {
				'id'            : instance.id,
				'blog_url'      : instance.blog_url or '#',
				'color'         : instance.color,
				'connected'     : instance.state == 'validate',
				'category_count': instance.channel_categories,
				'customer_count': instance.channel_customers,
				'order_count'   : instance.channel_orders,
				'product_count' : instance.channel_products,
			}
			image = instance.image
			image = image and f'data:image/jpeg;charset=utf-8;base64,{image.decode("utf-8")}' or ''
			instance_data[instance.name].update(image=image)

		return {
			'line_data': {'labels':labels,'data':data},
			'instance_data': instance_data,
		}

	@http.route('/multichannel/fetch_dashboard_data/<int:channel_id>',type='json',auth='user')
	def fetch_instance_dashboard_data(self,channel_id,period,**kw):
		labels = []
		instance = request.env['multi.channel.sale'].browse(channel_id)
		data = {
			'id'            : channel_id,
			'name'          : instance.name,
			'channel'       : instance.channel,
			'channel_name'  : dict(instance.fields_get(['channel'])['channel']['selection']).get(instance.channel),
			'color'         : instance.color,
			'connected'     : instance.state == 'validate',
			'store_url'     : instance.store_url and instance.store_url+'#reviews' or '#',
			'product_count' : [],
			'order_count'   : [],
			'category_count': [],
			'customer_count': [],
		}
		image = instance.image
		image = image and f'data:image/jpeg;charset=utf-8;base64,{image.decode("utf-8")}' or ''
		data.update(image=image)

		if period == 'year':
			year = fields.date.today().year
			labels = [
				'January', 'February',
				'March', 'April', 'May',
				'June', 'July', 'August',
				'September', 'October',
				'November', 'December',
			]
			request._cr.execute(f"""
				SELECT to_char(p.create_date,'Month') as month,COUNT(p.id)
					FROM channel_template_mappings m
					LEFT JOIN product_template p
						ON m.template_name = p.id
					WHERE EXTRACT(YEAR FROM p.create_date) = {year}
						AND m.channel_id = {channel_id}
					GROUP BY 1
			""")
			product_counts = {data['month'].strip():data['count'] for data in request._cr.dictfetchall()}

			request._cr.execute(f"""
				SELECT to_char(o.date_order,'Month') as month,COUNT(o.id)
					FROM channel_order_mappings m
					LEFT JOIN sale_order o
						ON m.odoo_order_id = o.id
					WHERE EXTRACT(YEAR FROM o.date_order) = {year}
						AND m.channel_id = {channel_id}
					GROUP BY 1
			""")
			order_counts = {data['month'].strip():data['count'] for data in request._cr.dictfetchall()}

			request._cr.execute(f"""
				SELECT to_char(c.create_date,'Month') as month,COUNT(c.id)
					FROM channel_category_mappings m
					LEFT JOIN product_category c
						ON m.odoo_category_id = c.id
					WHERE EXTRACT(YEAR FROM c.create_date) = {year}
						AND m.channel_id = {channel_id}
					GROUP BY 1
			""")
			category_counts = {data['month'].strip():data['count'] for data in request._cr.dictfetchall()}

			request._cr.execute(f"""
				SELECT to_char(c.create_date,'Month') as month,COUNT(c.id)
					FROM channel_partner_mappings m
					LEFT JOIN res_partner c
						ON m.odoo_partner_id = c.id
					WHERE EXTRACT(YEAR FROM c.create_date) = {year}
						AND m.channel_id = {channel_id}
					GROUP BY 1
			""")
			customer_counts = {data['month'].strip():data['count'] for data in request._cr.dictfetchall()}

			for month in labels:
				data['product_count'].append(product_counts.get(month,0))
				data['order_count'].append(order_counts.get(month,0))
				data['category_count'].append(category_counts.get(month,0))
				data['customer_count'].append(customer_counts.get(month,0))

		request._cr.execute(f"""
			SELECT COUNT(id) as to_export
				FROM product_template
				WHERE id NOT IN (
					SELECT DISTINCT template_name
						FROM channel_template_mappings
						WHERE channel_id = {channel_id}
				)
		""")
		product_counts = request._cr.dictfetchall()[0]
		request._cr.execute(f"""
			SELECT COUNT(need_sync) as mapped, COUNT(NULLIF('no',need_sync)) as to_update
				FROM channel_template_mappings
				WHERE channel_id = {channel_id}
		""")
		product_counts.update(request._cr.dictfetchall()[0])
		request._cr.execute(f"""
			SELECT type,COUNT(type)
				FROM channel_template_mappings m
				LEFT JOIN product_template p
					On m.template_name = p.id
				WHERE m.channel_id = {channel_id}
				GROUP BY type
		""")
		types = {'product':'Product','service':'Service'}
		for p in request._cr.dictfetchall():
			product_counts.setdefault('types',[]).append(types.get(p['type']))
			product_counts.setdefault('counts',[]).append(p['count'])

		request._cr.execute(f"""
			SELECT COUNT(need_sync) as mapped
				FROM channel_order_mappings
				WHERE channel_id = {channel_id}
		""")
		order_counts = request._cr.dictfetchall()[0]
		request._cr.execute(f"""
			SELECT
				COUNT(NULLIF(TRUE,is_delivered)) as to_deliver,
				COUNT(NULLIF(TRUE,is_invoiced)) as to_invoice
				FROM channel_order_mappings
				WHERE channel_id = {channel_id}
		""")
		order_counts.update(request._cr.dictfetchall()[0])
		states = {
			'draft' : 'Quotation',
			'sent'  : 'Quotation Sent',
			'sale'  : 'Sales Order',
			'done'  : 'Done',
			'cancel': 'Cancelled',
		}
		request._cr.execute(f"""
			SELECT o.state,COUNT(o.state)
				FROM channel_order_mappings m
				LEFT JOIN sale_order o
					On m.odoo_order_id = o.id
				WHERE m.channel_id = {channel_id}
				GROUP BY o.state
		""")
		for o in request._cr.dictfetchall():
			order_counts.setdefault('types',[]).append(states.get(o['state']))
			order_counts.setdefault('counts',[]).append(o['count'])

		request._cr.execute(f"""
			SELECT COUNT(id) as to_export
				FROM product_category
				WHERE id NOT IN (
					SELECT DISTINCT odoo_category_id
						FROM channel_category_mappings
						WHERE channel_id = {channel_id}
				)
		""")
		category_counts = request._cr.dictfetchall()[0]
		request._cr.execute(f"""
			SELECT COUNT(need_sync) as mapped, COUNT(NULLIF('no',need_sync)) as to_update
				FROM channel_category_mappings
				WHERE channel_id = {channel_id}
		""")
		category_counts.update(request._cr.dictfetchall()[0])

		request._cr.execute(f"""
			SELECT COUNT(id) as to_export
				FROM res_partner
				WHERE id NOT IN (
					SELECT DISTINCT odoo_partner_id
						FROM channel_partner_mappings
						WHERE channel_id = {channel_id}
				)
		""")
		customer_counts = request._cr.dictfetchall()[0]
		request._cr.execute(f"""
			SELECT COUNT(need_sync) as mapped, COUNT(NULLIF('no',need_sync)) as to_update
				FROM channel_partner_mappings
				WHERE channel_id = {channel_id}
		""")
		customer_counts.update(request._cr.dictfetchall()[0])
		return {
			'labels': labels,
			'data'  : data,
			'counts': {
				'product' : product_counts,
				'order'   : order_counts,
				'category': category_counts,
				'customer': customer_counts,
			},
		}
