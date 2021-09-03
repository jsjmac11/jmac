odoo.define('odoo_multi_channel_sale.backend.dashboard',function (require) {
	'use strict'

	var AbstractAction = require('web.AbstractAction')
	var ajax = require('web.ajax')
	var core = require('web.core')

	var MultichannelDashboard = AbstractAction.extend({
		template: 'multichannel_dashboard_template',
		jsLibs: [
			'/web/static/lib/Chart/Chart.js',
		],
		events: {
			'click ._action': 'on_action',
			'change #line_date_change': 'reload_line_graph',
			'change #line_obj_change': 'reload_line_graph',
			'change #pie_obj_change': 'reload_pie_graph',
		},

		willStart () {
			var self = this
			return $.when(
				ajax.loadLibs(this),
				this._super(),
			).then(function () {
				return self.fetch_data()
			})
		},

		on_attach_callback () {
			this.render_line_graph()
			this.render_pie_graph()
		},

		reload_line_graph () {
			var self = this
			var selected_option = $('#line_obj_change option:selected').val()
			var line_chart_label = $('#line_chart_label')
			switch (selected_option) {
				case 'order':
					line_chart_label.text('Sales Orders')
					break
				case 'product':
					line_chart_label.text('Products')
					break
				case 'category':
					line_chart_label.text('Categories')
					break
				case 'customer':
					line_chart_label.text('Customers')
					break
				default:
					line_chart_label.text('')
			}

			$.when(
				self.fetch_data(
					selected_option,
					parseInt($('#line_date_change option:selected').val()),
				)
			).then(function () {
				return self.render_line_graph()
			})
		},

		reload_pie_graph () {
			var selected_option = $('#pie_obj_change option:selected').val()
			var pie_chart_label = $('#pie_chart_label')
			switch (selected_option) {
				case 'order':
					pie_chart_label.text('Sales Orders')
					break
				case 'product':
					pie_chart_label.text('Products')
					break
				case 'category':
					pie_chart_label.text('Categories')
					break
				case 'customer':
					pie_chart_label.text('Customers')
					break
				default:
					pie_chart_label.text('')
			}
			this.render_pie_graph(selected_option)
		},

		fetch_data (obj='order',days=7) {
			var self = this
			return this._rpc({
				route: '/multichannel/fetch_dashboard_data',
				params: {obj,days},
			}).then(function (result) {
				self.line_data = result.line_data
				self.instance_data = result.instance_data
				self.connected_count = Object.values(result.instance_data).reduce(
					(n,i) => n + (i.connected === true), 0
				)
			})
		},

		render_line_graph () {
			$('#line_chart').replaceWith($('<canvas/>',{id: 'line_chart'}))
			var self = this
			self.line_chart = new Chart('line_chart',{
				type: 'line',
				data: {
					labels: self.line_data.labels,
					datasets: self.line_data.data.map(i => ({
						borderColor: i.color,
						data: i.count,
						label: i.name,
						fill: false,
					})),
				},
				beginAtZero: false,
				options: {
					maintainAspectfirefoxRatio: false,
					legend: {
						display: false,
					},
					scales: {
						xAxes: [{
							gridLines: {
								display: false,
							},
						}],
						yAxes: [{
							gridLines: {
								display: false,
							},
							ticks: {
								precision: 0,
							},
						}],
					},
				},
			})
		},

		render_pie_graph (obj='order') {
			$('#pie_chart').replaceWith($('<canvas/>',{id: 'pie_chart'}))
			var self = this
			self.pie_chart = new Chart('pie_chart',{
				type: 'pie',
				data: {
					labels: Object.keys(self.instance_data),
					datasets: [{
						backgroundColor: Object.values(self.instance_data).map(i => i['color']),
						data: Object.values(self.instance_data).map(i => i[obj+'_count']),
					}],
				},
				options: {
					maintainAspectRatio: false,
					cutoutPercentage: 45,
					legend: {
						position: 'bottom',
						labels: {
							usePointStyle: true,
						},
					},
				},
			})
		},

		on_action (e) {
			e.preventDefault()
			var target = $(e.currentTarget)
			var action = target.data('action')
			var object = target.data('object')
			var channel_id = target.data('channel')

			switch (action) {
				case 'import':
					return this.do_action('odoo_multi_channel_sale.open_import_wizard_action')
				case 'export':
					return this.do_action('odoo_multi_channel_sale.open_export_wizard_action')
				case 'open':
					return this.do_action({
						name: 'Instance',
						type: 'ir.actions.act_window',
						res_model: 'multi.channel.sale',
						views: [[false,'form']],
						target: 'main'
					})
			}

			if (object && channel_id) {
				var res_model
				switch (object) {
					case 'product':
						res_model = 'channel.template.mappings'
						break
					case 'order':
						res_model = 'channel.order.mappings'
						break
					case 'category':
						res_model = 'channel.category.mappings'
						break
					case 'customer':
						res_model = 'channel.partner.mappings'
						break
				}
				if (res_model)
					return this.do_action({
						name: 'Mapping',
						type: 'ir.actions.act_window',
						res_model,
						domain: [['channel_id','=',channel_id]],
						views: [[false,'list'],[false,'form']],
						target: 'main',
					})
			}

			if (channel_id)
				return this.do_action({
					type: 'ir.actions.client',
					tag: 'dashboard_instance',
					params: {id: channel_id},
				})
		},
	})

	var InstanceDashboard = AbstractAction.extend({
		template: 'instance_dashboard_template',
		jsLibs: [
			'/web/static/lib/Chart/Chart.js',
		],
		events: {
			'click ._action': 'on_action',
			'click ._graph_button:not(.active)': 'change_graph',
		},

		init (parent,action) {
			this.id = action.params.id
			this._super(parent,action)
		},

		willStart () {
			$('.o_action_manager').empty()
			var self = this
			return $.when(
				ajax.loadLibs(this),
				this._super(),
			).then(function () {
				return self.fetch_data()
			})
		},

		on_attach_callback () {
			for (let obj of ['product','order','category','customer'])
				this.render_line_graph(obj)
			$('[data-toggle="tooltip"]').tooltip()
		},

		change_graph (e) {
			var target = $(e.currentTarget)
			target.siblings('.active').removeClass('active')
			target.addClass('active')

			this['render_'+target.data('mode')+'_graph'](target.data('object'))
		},

		fetch_data () {
			var self = this
			return this._rpc({
				route: '/multichannel/fetch_dashboard_data/'+this.id,
				params: {period: 'year'}
			}).then(function (result) {
				self.labels = result.labels
				self.data = result.data
				self.counts = result.counts
			})
		},

		render_line_graph (obj) {
			$('#'+obj+'_chart').replaceWith($('<canvas/>',{id: obj+'_chart'}))
			var self = this
			var data = self.data[obj+'_count']
			if (data.length)
				self.chart = new Chart(obj+'_chart',{
					type: 'line',
					data: {
						labels: self.labels,
						datasets: [{
							data,
							borderColor: self.data.color,
							backgroundColor: self.data.color+'66',
						}],
					},
					options: {
						maintainAspectRatio: false,
						legend: {
							display: false,
						},
						scales: {
							xAxes: [{
								gridLines: {
									display: false,
								}
							}],
							yAxes: [{
								gridLines: {
									display: false,
								},
								ticks: {
									precision: 0,
								},
							}],
						},
					},
				})
		},

		render_pie_graph (obj) {
			$('#'+obj+'_chart').replaceWith($('<canvas/>',{id: obj+'_chart'}))
			var self = this
			var labels = self.counts[obj].types
			if (labels) {
				var backgroundColor = labels.map(x=>self.data.color+'66')
				var borderColor = labels.map(x=>self.data.color)
				self.pie_chart = new Chart(obj+'_chart',{
					type: 'pie',
					data: {
						labels,
						datasets: [{
							backgroundColor,
							borderColor,
							hoverBackgroundColor: borderColor,
							data: self.counts[obj].counts,
						}],
					},
					options: {
						maintainAspectRatio: false,
						legend: {
							display: false,
						},
					},
				})
			}
		},

		on_action (e) {
			e.preventDefault()
			var self = this
			var target = $(e.currentTarget)

			var action = target.data('action')
			var instance = target.data('instance')
			var obj = target.data('obj')
			var type = target.data('type')
			var feed = target.data('feed')
			var state = target.data('state')
			var report = target.data('report')
			var count = target.data('count')
			var reload = target.data('reload')

			if (reload)
				target[0].classList.add('fa-spin')

			if (action && instance)
				switch (action) {
					case 'import':
						return this.do_action('odoo_multi_channel_sale.open_import_wizard_action', {
							additional_context: {
								default_channel_id: instance,
							},
						})
					case 'export':
						return this.do_action('odoo_multi_channel_sale.open_export_wizard_action', {
							additional_context: {
								default_channel_id: instance,
							},
						})
					case 'open':
						return this.do_action({
							name: 'Instance',
							type: 'ir.actions.act_window',
							res_model: 'multi.channel.sale',
							res_id: instance,
							views: [[false,'form']],
							target: 'main'
						})
					case 'evaluate':
						return this.do_action('odoo_multi_channel_sale.action_feed_sync', {
							additional_context: {
								default_channel_id: instance,
							},
						})
				}

			if (obj && report)
				return self.do_action({
					name: 'Report',
					type: 'ir.actions.act_window',
					res_model: 'channel.synchronization',
					domain: [
						['channel_id','=',instance],
						['action_on','=',obj],
						['status','=',report],
					],
					views: [
						[false,'list'],
						[false,'form'],
					],
					target: 'main',
				})

			if (obj && reload)
				return this._rpc({
					model: 'channel.order.mappings',
					method: 'update_order_mapping_status',
					args: [instance],
				}).then(
					location.reload()
				)

			if (obj) {
				var name,res_model,domain,mapping_model,odoo_mapping_field
				switch (obj) {
					case 'product':
						name = 'Product'
						res_model = 'product.template'
						mapping_model = 'channel.template.mappings'
						odoo_mapping_field = 'odoo_template_id'
						break
					case 'order':
						name = 'Order'
						res_model = 'sale.order'
						mapping_model = 'channel.order.mappings'
						odoo_mapping_field = 'odoo_order_id'
						break
					case 'category':
						name = 'Category'
						res_model = 'product.category'
						mapping_model = 'channel.category.mappings'
						odoo_mapping_field = 'odoo_category_id'
						break
					case 'customer':
						name = 'Customer'
						res_model = 'res.partner'
						mapping_model = 'channel.partner.mappings'
						odoo_mapping_field = 'odoo_partner_id'
						break
				}
				if (name)
					if (count) {
						switch (count) {
							case 'mapped':
								domain = [['channel_id','=',instance]]
								break
							case 'to_update':
								domain = [['channel_id','=',instance],['need_sync','=','yes']]
								break
							case 'to_deliver':
								domain = [['channel_id','=',instance],['is_delivered','=',false]]
								break
							case 'to_invoice':
								domain = [['channel_id','=',instance],['is_invoiced','=',false]]
								break
						}
						if (domain)
							return self.do_action({
								name: 'Mapping',
								type: 'ir.actions.act_window',
								res_model: mapping_model,
								domain,
								views: [
									[false,'list'],
									[false,'form'],
								],
								target: 'main',
							})
					}
					return this._rpc({
						model: 'multi.channel.sale',
						method: 'open_record_view',
						args: [instance],
						context: {
							mapping_model,
							odoo_mapping_field,
						},
					}).then(function(result) {
						var domain = result.domain
						if (count && count === 'to_export')
							domain[0][1] = 'not in'
						if (type) {
							if (obj === 'product') {
								if (type === 'multi_variant')
									domain.push(['attribute_line_ids','!=',false])
								else
								if (type === 'single_variant')
									domain.push(['attribute_line_ids','=',false])
							}
							else
							if (obj === 'order') {
								domain.push(['state','=',type])
							}
							else
							if (obj === 'customer') {
								if (type === 'other')
									domain.push(['type','not in',['invoice','delivery']])
								else
									domain.push(['type','=',type])
							}
						}
						return self.do_action({
							name,
							type: 'ir.actions.act_window',
							res_model,
							domain,
							views: [
								[false,'list'],
								[false,'form'],
							],
							target: 'main',
						})
					})
			}

			if (feed && state)
				return self.do_action({
					name: 'Feed',
					type: 'ir.actions.act_window',
					res_model: feed,
					domain: [
						['channel_id','=',instance],
						['state','=',state],
					],
					views: [
						[false,'list'],
						[false,'form'],
					],
					target: 'main',
				})
		},
	})

	core.action_registry.add('dashboard_multichannel',MultichannelDashboard)
	core.action_registry.add('dashboard_instance',InstanceDashboard)
})
