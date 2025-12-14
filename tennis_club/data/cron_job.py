import json
from odoo import models, fields


class TrainingJob(models.Model):
    _name = "training.job"
    _description = "Background job for slot generation"

    name = fields.Char()
    user_id = fields.Many2one("res.users")
    court_id = fields.Many2one("centers.model")
    date_list = fields.Text()
    state = fields.Selection([
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="pending")

    error_message = fields.Text()

    def run_job(self):
        """ Run """
        for job in self:
            job.state = "running"
            try:
                dates = json.loads(job.date_list or "[]")
                generator = self.env["training.generator"]
                generator.generate_all_slots(dates, job.user_id)
                job.state = "done"
            except Exception as e:
                job.state = "failed"
                job.error_message = str(e)

