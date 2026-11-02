import copy
import unittest
import runtime_protocol as protocol


class JobProtocolTests(unittest.TestCase):
    def request(self,command,payload=None):
        return dict(protocol_version=1,client_id='test',request_id='read',expected_revision=None,command=command,payload=payload or {})
    def reply(self,draft):return dict(request_id='read',status='OK',runtime_generation='first',draft=draft)

    def test_missing_or_invented_jobs_shape_refuses(self):
        for body in ({},[],{'status':'OK'},{'revision':0}):
            with self.subTest(body=body),self.assertRaises((ValueError,TypeError)):protocol.validate_response(self.reply(body),self.request('jobs'))
    def test_malformed_job_mutation_result_refuses(self):
        request=self.request('job-submit');request['expected_revision']=1
        for result in ({},{'job':None},{'job':'valid','execution_approved':True}):
            with self.assertRaises(ValueError):protocol.validate_response(self.reply(dict(status='OK',revision=2,result=result)),request)
    def test_bad_artifact_hash_or_corruption_text_refuses(self):
        for integrity,text,sha in [('VALID','wrong','a'*64),('CORRUPT_OR_MISSING','untrusted','a'*64)]:
            with self.assertRaises(ValueError):protocol.validate_response(self.reply(dict(attempt='a',kind='draft',sha256=sha,provider=dict(kind='fake',model='',digest=''),integrity=integrity,text=text)),self.request('job-artifact',dict(attempt='a')))

    def test_valid_artifact_and_provider_roundtrip(self):
        import hashlib
        artifact=dict(attempt='a',kind='draft',sha256=hashlib.sha256(b'draft').hexdigest(),provider=dict(kind='fake',model='',digest=''),integrity='VALID',text='draft')
        reply=self.reply(artifact)
        self.assertEqual(protocol.validate_response(reply,self.request('job-artifact',dict(attempt='a'))),reply)
    def test_invalid_event_order_refuses(self):
        events=[dict(revision=1,kind='RECOVERY',job=None,attempt=None,detail={})]*2
        with self.assertRaises(ValueError):protocol.validate_response(self.reply(events),self.request('job-events',dict(after=0,limit=2)))
    def test_unknown_refusal_and_missing_identity_refuse(self):
        for error in ('APPROVED','',None):
            with self.assertRaises(ValueError):protocol.validate_response(self.reply(dict(status='REFUSED',error=error,revision=0,result={})),self.request('jobs'))
        reply=self.reply({});reply['request_id']='different'
        with self.assertRaises(ValueError):protocol.validate_response(reply,self.request('jobs'))
    def test_mutations_require_revision_and_internal_commands_never_parse(self):
        for command in protocol.JOB_MUTATIONS:
            with self.assertRaises(ValueError):protocol.validate_request(self.request(command))
        for command in ('claim','finish','job-claim','job-finish'):
            with self.assertRaises(ValueError):protocol.validate_request(self.request(command))


if __name__=='__main__':unittest.main(verbosity=2)
