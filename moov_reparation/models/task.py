from odoo import models, api, fields, _


class ProjectTask(models.Model):
	_inherit = 'project.task'

	reparation_number = fields.Char(string="Reparation Number")

	@api.model_create_multi
	def create(self, vals_list):
		task_ids = super(ProjectTask, self).create(vals_list)
		for task in task_ids:
			task.reparation_number = self.env['ir.sequence'].sudo().next_by_code('project.task')
		return task
