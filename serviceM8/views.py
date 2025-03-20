
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from accounts.models import GHLAuthCredentials
from django.http import JsonResponse
from urllib.parse import urlparse
import threading
from serviceM8.models import ServiceM8Log
import traceback
from serviceM8.utils import fetch_servicem8_job, fetch_servicem8_client, fetch_company_contact, fetch_job_contact, get_or_create_client, get_or_create_job

lock = threading.Lock()




@csrf_exempt
def servicem8_webhook2(request):
    if request.method == 'OPTIONS':
        response = HttpResponse()
        origin = request.headers.get('Origin', '')
        parsed_origin = urlparse(origin)

        if parsed_origin.netloc.endswith(".servicem8.com") or parsed_origin.netloc == "servicem8.com":
            response['Access-Control-Allow-Origin'] = origin

        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response['Access-Control-Max-Age'] = '86400'
        return response
    
    if request.method == 'POST':
        log_entry = ServiceM8Log(status="started", event_type="webhook_received")
        try:
            webhook_data = json.loads(request.body)
            event_type = webhook_data.get('eventType')
            event_data = webhook_data.get('eventData', {})
            
            # Update log with initial data
            log_entry.event_type = event_type
            log_entry.set_servicem8_data(webhook_data)
            log_entry.save()
            
            if event_type == 'Webhook_Subscription' and event_data.get('object') == 'Job':
                entries = event_data.get('entry', [])
                if not entries:
                    log_entry.status = "warning"
                    log_entry.error_message = "No entries found in webhook data"
                    log_entry.save()
                    return JsonResponse({'status': 'success', 'message': 'No entries found in webhook data'}, status=200)
                
                job_uuid = entries[0].get('uuid')
                log_entry.job_uuid = job_uuid
                log_entry.save()
                
                auth_data = webhook_data.get('rawEvent', {}).get('auth', {})
                access_token = auth_data.get('accessToken')
                
                if not access_token:
                    log_entry.status = "error"
                    log_entry.error_message = "Access token required from ServiceM8"
                    log_entry.save()
                    return JsonResponse({"status": "success", "message": "Access token required from ServiceM8"}, status=200)
                
                job_data = fetch_servicem8_job(job_uuid, access_token)
                if not job_data:
                    log_entry.status = "error"
                    log_entry.error_message = "Failed to fetch job data"
                    log_entry.save()
                    return JsonResponse({'status': 'success', 'message': 'Failed to fetch job data'}, status=200)
                
                company_uuid = job_data.get('company_uuid')
                if not company_uuid:
                    log_entry.status = "error"
                    log_entry.error_message = "Client details needed to create job"
                    log_entry.save()
                    return JsonResponse({'status': 'success', 'message': 'Client details needed to create job'}, status=200)
                
                log_entry.client_uuid = company_uuid
                log_entry.save()
                
                client_data = fetch_servicem8_client(company_uuid, access_token)
                if not client_data:
                    log_entry.status = "error"
                    log_entry.error_message = "Failed to fetch client data from ServiceM8"
                    log_entry.save()
                    return JsonResponse({'status': 'success', 'message': 'Failed to fetch client data from ServiceM8'}, status=200)
                
                job_contact = fetch_job_contact(job_data.get("uuid"), access_token)
                if not job_contact:
                    company_contact = fetch_company_contact(client_data.get('uuid'), access_token)
                    job_contact = company_contact
                    if not job_contact:
                        job_contact = [{}]
                        log_entry.error_message = "No contact data found for job or company"
                        log_entry.save()
                
                ghl_credentials = GHLAuthCredentials.objects.first()
                if not ghl_credentials:
                    log_entry.status = "error"
                    log_entry.error_message = "GHL authentication credentials not found"
                    log_entry.save()
                    return JsonResponse({'status': 'success', 'message': 'GHL authentication credentials not found'}, status=200)

                ghl_token = ghl_credentials.access_token
                with lock:
                    # Create/update client
                    try:
                        client = get_or_create_client(client_data, job_contact[-1], ghl_token)
                        log_entry.client_link_successful = True
                        log_entry.ghl_client_id = client.ghl_id
                    except Exception as client_error:
                        log_entry.status = "partial_error"
                        log_entry.error_message = f"Client creation error: {str(client_error)}"
                        log_entry.stack_trace = traceback.format_exc()
                        log_entry.save()
                    
                    # Create/update job
                    try:
                        job = get_or_create_job(job_data, client, ghl_token)
                        log_entry.job_link_successful = True
                        log_entry.ghl_job_id = job.ghl_id
                    except Exception as job_error:
                        log_entry.status = "partial_error" if log_entry.client_link_successful else "error"
                        log_entry.error_message = f"{log_entry.error_message}\nJob creation error: {str(job_error)}"
                        log_entry.stack_trace = traceback.format_exc()
                        log_entry.save()
                
                if log_entry.client_link_successful and log_entry.job_link_successful:
                    log_entry.status = "success"
                    log_entry.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Successfully processed job {job_uuid}',
                    'client_id': client.ghl_id if log_entry.client_link_successful else None,
                    'job_id': job.ghl_id if log_entry.job_link_successful else None
                })
        except Exception as e:
            log_entry.status = "error"
            log_entry.error_message = str(e)
            log_entry.stack_trace = traceback.format_exc()
            log_entry.save()
            return JsonResponse({'status': 'success', 'message': str(e)}, status=200)


