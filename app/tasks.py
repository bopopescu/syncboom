#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

import json
import sys
import time
from flask import render_template
from rq import get_current_job
from app import create_app, db
from app.models import Task, Mapping
from app.email import send_email
from trello_team_sync import perform_request, process_master_card

app = create_app()
app.app_context().push()


def run_mapping(mapping_id, run_type, elem_id):
    seconds = 5
    mapping = Mapping.query.filter_by(id=mapping_id).first()
    try:
        job = get_current_job()
        _set_task_progress(0)
        app.logger.info('Starting task for mapping %d, %s %s' %
            (mapping_id, run_type, elem_id))
        if run_type in ("card", "list", "board"):
            args_from_app = {
                "destination_lists": json.loads(mapping.destination_lists),
                "key": mapping.key,
                "token": mapping.token
            }
            if run_type == "card":
                master_cards = [perform_request("GET", "cards/%s" % elem_id,
                    key=mapping.key, token=mapping.token)]
            elif run_type in ("list", "board"):
                master_cards = perform_request("GET", "%s/%s/cards" %
                    (run_type, elem_id),
                    key=mapping.key, token=mapping.token)
            for idx, master_card in enumerate(master_cards):
                app.logger.info("Processing master card %d/%d - %s" %
                    (idx+1, len(master_cards), master_card["name"]))
                output = process_master_card(master_card, args_from_app)
                if idx < len(master_cards)-1:
                    _set_task_progress(int(100.0 * (idx+1) / len(master_cards)))
        else:
            app.logger.error("Invalid task, ignoring")
        _set_task_progress(100)
        job.save_meta()
        app.logger.info('Completed task for mapping %d, %s %s' %
            (mapping_id, run_type, elem_id))
    except:
        _set_task_progress(100)
        app.logger.error(
            'run_mapping: Unhandled exception while running task %d %s %s' %
            (mapping_id, run_type, elem_id), exc_info=sys.exc_info())


def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = Task.query.get(job.get_id())
        task.user.add_notification('task_progress', {'task_id': job.get_id(),
                                                     'progress': progress})
        if progress >= 100:
            task.complete = True
        db.session.commit()
