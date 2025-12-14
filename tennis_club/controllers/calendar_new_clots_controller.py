import logging
import json

from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class TrainingController(http.Controller):

    @http.route("/tennis_club/get_new_slots", auth="user", type="json", methods=["POST"])
    def get_virtual_dates(self, **kwargs):
        """ Get Center Information and Start Creating Slots"""
        user = request.env.user
        employee = request.env["hr.employee"].sudo().search([("user_id", "=", user.id)], limit=1)
        if not employee or not employee.working_center_id:
            _logger.warning("No employee or center found for user %s", user.id)
            return {"status": "ok", "working_center_id": None, "courts": []}

        center_id = employee.working_center_id
        courts_record_ids = request.env["centers.model"].sudo().search([("parent_center_id", "=", center_id.id)])
        courts_names = [court_id.name for court_id in courts_record_ids] if courts_record_ids else []

        if not courts_record_ids:
            _logger.warning("No courts found for center %s", center_id.id)
            return {"working_center_id": center_id.name, "courts":[]}

        dates = kwargs.get("dates", [])
        if not dates:
                return {
                "status": "ok",
                "working_center_id": center_id.name,
                "courts": courts_names
                }

        valid_dates = []
        for date_str in dates:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                valid_dates.append(date_str)
            except ValueError:
                _logger.warning("Invalid date format: %s", date_str)

        if not valid_dates:
            return {"status": "ok", "working_center_id": None, "courts": []}

        date_ranges = []
        for date_str in dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                _logger.warning("Invalid date format: %s", date_str)
                continue
            day_start = datetime.combine(date_obj, datetime.min.time())
            day_end = datetime.combine(date_obj, datetime.max.time())
            date_ranges.append((day_start, day_end))

        TrainingJob = request.env["training.job"].sudo()
        TrainingModel = request.env["training.model"].sudo()

        for court_id in courts_record_ids:
            job_name = f"Generate slots for {court_id.name} ({valid_dates[0]} - {valid_dates[-1]})"
            job_exist = TrainingJob.search_count([
                ("name", "=", job_name),
                ("state","=","pending")
            ])
            if job_exist == 0:
                import pytz

                utc = pytz.UTC
                client_tz = pytz.timezone(request.context.get("tz", "UTC"))

                start_client = utc.localize(date_ranges[0][0]).astimezone(client_tz)
                end_client = utc.localize(date_ranges[-1][1]).astimezone(client_tz)

                free_and_non_working_slots_exist = TrainingModel.search_count([
                    ("center_id", "=", center_id.id),
                    ("tennis_court_id", "=", court_id.id),
                    ("time_begin", "<=", end_client),
                    ("time_finish", ">=", start_client),
                    "|",
                    ("name", "=", "free slot"),
                    ("name", "=", "non-working hours"),
                ])

                if free_and_non_working_slots_exist == 0:
                    TrainingJob.create({
                        "name": job_name,
                        "user_id": user.id,
                        "court_id": court_id.id,
                        "date_list": json.dumps(valid_dates),
                        "state": "pending",
                    })
                    _logger.info("Queued training job '%s' for court %s", job_name, court_id.id)

        return {
            "status": "ok",
            "working_center_id": center_id.name,
            "courts": courts_names
        }