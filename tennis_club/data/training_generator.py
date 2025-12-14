import logging
import json
from datetime import datetime, timedelta, time, timezone
from odoo import models, api

_logger = logging.getLogger(__name__)


class TrainingGenerator(models.Model):
    _name = "training.generator"
    _description = "Logic for generating training slots"

    def _load_environment(self, user):
        """ Load Environment (employee, center, courts) """
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id)], limit=1
        )
        if not employee:
            raise Exception("Employee not found")

        center = employee.working_center_id
        if not center or not center.working_hours_center_utc:
            raise Exception("Center has no working hours")

        courts = self.env["centers.model"].sudo().search([
            ("parent_center_id", "=", center.id)
        ])

        return employee, center, courts

    def _parse_working_hours(self, center):
        """ Parse Working Hours """
        try:
            return json.loads(center.working_hours_center_utc or "{}")
        except Exception:
            _logger.exception(
                "Invalid working hours JSON: %s",
                center.working_hours_center_utc
            )
            raise Exception("Invalid working hours JSON")

    def _to_time(self, value):
        """ Change Time Data """
        return time(*map(int, value.split(":")))

    def _get_work_and_nonwork(self, working_hours, date_obj):
        """ Get Work and Nonwork Time """
        weekday = str(date_obj.isoweekday())
        intervals = working_hours.get(weekday, [])

        work = []
        for interval in intervals:
            start_s, end_s = interval.split("-")
            work.append((self._to_time(start_s), self._to_time(end_s)))
        work.sort()

        full_start = time(0, 0)
        full_end = time(0, 0)  # конец суток (следующий день)
        non_work = []

        if not work:
            non_work.append((full_start, full_end))
        else:
            if work[0][0] > full_start:
                non_work.append((full_start, work[0][0]))

            for (s1, e1), (s2, e2) in zip(work, work[1:]):
                if e1 < s2:
                    non_work.append((e1, s2))

            if work[-1][1] != full_end:
                non_work.append((work[-1][1], full_end))

        return work, non_work

    def _merge_intervals(self, intervals):
        """ Merge Intervals """
        if not intervals:
            return []

        intervals.sort()
        merged = [[intervals[0][0], intervals[0][1]]]

        for s, e in intervals[1:]:
            if s > merged[-1][1]:
                merged.append([s, e])
            else:
                merged[-1][1] = max(merged[-1][1], e)

        return merged

    def _dt(self, date_obj, t):
        """Creates a UTC datetime, correctly handling 00:00"""
        dt = datetime.combine(date_obj, t)
        if t == time(0, 0):
            dt += timedelta(days=1)
        return dt

    @api.model
    def generate_non_working(self, dates, user):
        """ GENERATE NON-WORKING """
        _logger.info("### GENERATE NON-WORKING ###")

        _, center, courts = self._load_environment(user)
        working_hours = self._parse_working_hours(center)
        today = datetime.now(timezone.utc).date()

        for date_str in sorted(dates):
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            if date_obj < today:
                continue

            _, non_work = self._get_work_and_nonwork(working_hours, date_obj)

            for court in courts:
                for start_t, end_t in non_work:
                    start_utc = datetime.combine(date_obj, start_t)
                    end_utc = self._dt(date_obj, end_t)

                    existing = self.env["training.model"].sudo().search_count([
                        ("center_id", "=", center.id),
                        ("tennis_court_id", "=", court.id),
                        ("instructor_id", "=", 25),
                        ("time_begin", "<", end_utc),
                        ("time_finish", ">", start_utc),
                    ])
                    if existing:
                        continue

                    before = self.env["training.model"].sudo().search([
                        ("center_id", "=", center.id),
                        ("tennis_court_id", "=", court.id),
                        ("instructor_id", "=", 25),
                        ("time_finish", "=", start_utc),
                        ("status", "=", "unavailable"),
                    ], limit=1)

                    after = self.env["training.model"].sudo().search([
                        ("center_id", "=", center.id),
                        ("tennis_court_id", "=", court.id),
                        ("instructor_id", "=", 25),
                        ("time_begin", "=", end_utc),
                        ("status", "=", "unavailable"),
                    ], limit=1)

                    if before and after:
                        before.write({"time_finish": after.time_finish})
                        after.unlink()
                    elif before:
                        before.write({"time_finish": end_utc})
                    elif after:
                        after.write({"time_begin": start_utc})
                    else:
                        self.env["training.model"].sudo().create({
                            "name": "non-working hours",
                            "center_id": center.id,
                            "tennis_court_id": court.id,
                            "product_training_id": 1,
                            "instructor_id": 25,
                            "time_begin": start_utc,
                            "time_finish": end_utc,
                            "status": "unavailable",
                        })

    @api.model
    def generate_free_slots(self, dates, user):
        """ GENERATE FREE SLOTS """
        _logger.info("### GENERATE FREE SLOTS ###")

        _, center, courts = self._load_environment(user)
        working_hours = self._parse_working_hours(center)

        today = datetime.now(timezone.utc).date()
        slot = timedelta(hours=1)
        to_create = []

        for date_str in sorted(dates):
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            if date_obj < today:
                continue

            _, non_work = self._get_work_and_nonwork(working_hours, date_obj)

            day_start = datetime.combine(date_obj, time(0, 0))
            day_end = datetime.combine(date_obj + timedelta(days=1), time(0, 0))

            for court in courts:
                trainings = self.env["training.model"].sudo().search([
                    ("center_id", "=", center.id),
                    ("tennis_court_id", "=", court.id),
                    ("time_begin", "<", day_end),
                    ("time_finish", ">", day_start),
                    ("status", "!=", "cancelled"),
                ])

                busy = [(t.time_begin, t.time_finish) for t in trainings]

                for start_t, end_t in non_work:
                    s = datetime.combine(date_obj, start_t)
                    e = self._dt(date_obj, end_t)
                    busy.append((s, e))

                merged_busy = self._merge_intervals(busy)

                cur = day_start
                for b_start, b_end in merged_busy:
                    while cur + slot <= b_start:
                        to_create.append({
                            "name": "free slot",
                            "center_id": center.id,
                            "tennis_court_id": court.id,
                            "product_training_id": 1,
                            "instructor_id": 25,
                            "time_begin": cur,
                            "time_finish": cur + slot,
                            "status": "new",
                        })
                        cur += slot
                    cur = max(cur, b_end)

                while cur + slot <= day_end:
                    to_create.append({
                        "name": "free slot",
                        "center_id": center.id,
                        "tennis_court_id": court.id,
                        "product_training_id": 1,
                        "instructor_id": 25,
                        "time_begin": cur,
                        "time_finish": cur + slot,
                        "status": "new",
                    })
                    cur += slot

        if to_create:
            self.env["training.model"].sudo().create(to_create)

    @api.model
    def generate_all_slots(self, dates, user):
        """ Run Generate Slots """
        self.generate_non_working(dates, user)
        self.generate_free_slots(dates, user)
