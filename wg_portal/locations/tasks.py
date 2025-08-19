from celery import shared_task
from django.core.management import call_command
import logging

@shared_task
def fast_sync_stats_task():
	try:
		call_command('fast_sync_stats', '--quiet')
	except Exception as e:
		logging.error(f"fast_sync_stats_task error: {e}")

@shared_task
def save_peer_stats_task():
	try:
		call_command('save_peer_stats')
	except Exception as e:
		logging.error(f"save_peer_stats_task error: {e}")
