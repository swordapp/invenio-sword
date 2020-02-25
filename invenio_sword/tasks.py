import celery


@celery.shared_task
def fetch_by_reference_file(version_id):
    pass
