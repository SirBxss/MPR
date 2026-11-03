"""Synthetic complete cached return. No recording data or raw access."""
import csv,hashlib,json
from io import BytesIO, StringIO
import zipfile

from lane_residuals.domain.direct_speed_study import analyze, REVISION
from lane_residuals.domain.velocity_timing import TOPICS
from tests.io.velocity_timing_fixture import row, LOG, SOURCE


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,sort_keys=True)+'\n').encode()
def csv_data(rows):
    stream=StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
    for r in rows:writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()})
    return stream.getvalue().encode()

def make_files():
    p='study_attempt_003/probe/'
    files={'owner_launcher.py':b'synthetic controller','owner_entrypoint.py':b'synthetic entrypoint','recovery_evidence.py':b'synthetic evidence',
        'independent_review_note.private.md':b'synthetic helper GO','pinned_inputs/source_protocol_review.private.md':b'synthetic source GO',
        'pinned_inputs/previous_attempt_001.zip':b'synthetic earlier evidence','pinned_inputs/previous_attempt_002.zip':b'synthetic later evidence'}
    request={'revision':REVISION,'cases':[]};cases=[]
    for n in (1,2):
        oid=f'outing_{n:03d}';folder=p+oid+'/'
        targets=[row(i) for i in range(3)]
        for r in targets:
            source=int(r['estimate_source_time_ns_decimal_private'])
            r['speed_bracket_evidence']={'current_lower_timestamp_ns_decimal_private':str(source),'current_upper_timestamp_ns_decimal_private':str(source),
                'previous_lower_timestamp_ns_decimal_private':str(source-60_000_000),'previous_upper_timestamp_ns_decimal_private':str(source-40_000_000)}
        records=[{'topic':t,'log_ns':str(LOG+i*100_000_000-1),'publish_ns':str(SOURCE-2),'source_ns':str(SOURCE+i*100_000_000-(0 if i==0 else 1)),
            'value':10.,'qualifier':1,'outer_qualifier':2,'standstill_status':15,'nested_present':True,'non_default_decoded_fields':['value','qualifier','timestamp']} for t in TOPICS for i in range(3)]
        old={i:10. for i in range(3)};analysis,frames=analyze(records,targets,old)
        declared={'outing_id':oid,'recording_id':'synthetic','window_start_log_ns':str(LOG),'window_end_log_ns':str(LOG+300_000_000)}
        request['cases'].append(declared)
        audit=encoded({'rows':targets});inventory=encoded({'synthetic':True})
        cases.append({**declared,'analysis':analysis,'raw_sha256':'a'*64,'size_bytes':123,
            'raw_verification':{'sha256':'a'*64,'bytes':123},'binding':{'audit_sha256':sha(audit),'inventory_sha256':sha(inventory)}})
        files.update({folder+'original_candidate_audit.private.json':audit,folder+'original_inventory.private.json':inventory,
            folder+'old_speed.private.json':encoded(old),folder+'velocity_updates.private.csv':csv_data(records),folder+'frame_decisions.private.csv':csv_data(frames)})
    files['pinned_inputs/request.private.json']=encoded(request);pin=sha(files['pinned_inputs/request.private.json'])
    gate={'request_sha256':pin,'tree':'b'*40,'runtime_sha256':'c'*64,'independent_review_go_owner_attested':True,
        'review_note_sha256':sha(files['independent_review_note.private.md'])}
    files['source_gate.private.json']=encoded(gate)
    files['study_attempt_003/metadata_round_1/source_gate.private.json']=encoded(gate)
    gatepin=sha(files['source_gate.private.json']);sourcepin=sha(files['pinned_inputs/source_protocol_review.private.md'])
    receipt={'status':'complete','child_exit_code':0,'parent_timeout':False,'parent_interrupted':False,'metadata_only_retries':0,
        'metadata_rounds':[{'source_seal_exit_code':0,'study_child_exit_code':0,'gate_sha256':gatepin}],
        'helper_review_sha256':gate['review_note_sha256'],'source_review_sha256':sourcepin,'correct_source_review_sha256':sourcepin,
        'entrypoint_sha256':sha(files['owner_entrypoint.py']),'expected_reviewed_tree':gate['tree'],'runtime_sha256':gate['runtime_sha256'],'request_sha256':pin,
        'second_result_sha256':sha(files['pinned_inputs/previous_attempt_002.zip']),
        'first_return':{'previous_result_sha256':sha(files['pinned_inputs/previous_attempt_001.zip'])}}
    files['study_attempt_003/launcher_receipt.private.json']=encoded(receipt)
    report={'revision':REVISION,'status':'complete_bounded_direct_speed_development_study','phase':'complete','source':gate,
        'gate_sha256':gatepin,'request_sha256':pin,'claims_created':2,'raw_hash_started':True,'payload_decode_started':True,'cases':cases}
    for k in ('model_fitted','new_training_arrays_exported','training_dataset_modified','speed_feature_adopted','final_outings_exposed','physical_causal_availability_proven','cohort_wide_temporal_recovery_established'):report[k]=False
    files[p+'report.private.json']=encoded(report)
    for name in ('population_stations.private.csv','direct_speed_windows.png','direct_speed_windows.pdf','cached_population_difference.png','cached_population_difference.pdf'):files[p+name]=b'synthetic'
    for stage in ('seal','run'):
        for kind in ('stdout','stderr'):files[f'study_attempt_003/metadata_round_1/{stage}/{kind}.private.log']=b''
    return files

def pack(files,manifest=True):
    files=dict(files)
    if manifest:files['SHA256SUMS']=''.join(sha(raw)+'  '+name+'\n' for name,raw in files.items() if name!='SHA256SUMS').encode()
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in files.items():z.writestr(name,raw)
    return stream.getvalue()
