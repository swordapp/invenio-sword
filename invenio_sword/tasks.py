import celery


@celery.shared_task
def fetch_by_reference_files(record_id):
    pass


@celery.shared_task
def fetch_by_reference_file(object_id):
    pass
