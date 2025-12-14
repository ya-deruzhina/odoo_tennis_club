from datetime import datetime
from odoo import models, api

class TrainingGenerator(models.Model):
    _inherit = "training.model"
    _description = "Logic for generating training slots"

    @api.model
    def _auto_done_trainings(self):
        """ Cron Task to Delete New and Unavailable Trainings, Other to Done or Cancelled Status"""
        now = datetime.now()
        training_ids = self.search([("time_finish", "<=", now)])
        for training in training_ids:
            try:
                if training.status in ["reserved", "waiting_approve_cancel"]:
                    training.status = "done"
                elif training.status == "waiting_approve_reserve":
                    training.status = "cancelled"
                elif training.status in ["new", "unavailable"]:
                    training.unlink()
            except:
                continue
