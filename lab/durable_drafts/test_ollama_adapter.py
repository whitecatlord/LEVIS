import copy
import json
import threading
import unittest
from unittest.mock import patch
from ollama_adapter import OllamaDraftAdapter, AdapterRefused, strict_json, MAX_RESPONSE_BYTES

PIN = 'a' * 64
CLAIM = dict(goal='Draft only', inputs=[dict(name='x', text='source | exact\n', sha256='b'*64)], answers=[])


class AdapterTests(unittest.TestCase):
    def adapter(self):
        adapter = OllamaDraftAdapter('test:fixed', PIN)
        self.calls = []
        self.inventory = dict(models=[dict(name='test:fixed', digest=PIN)])
        self.result = dict(model='test:fixed', done=True, done_reason='stop', response='Draft.', eval_count=2)
        def request(method, path, value=None):
            self.calls.append((method, path, value))
            return copy.deepcopy(self.inventory if path == '/api/tags' else self.result)
        adapter._request = request
        return adapter

    def test_exact_inputs_preserved_and_no_tools_or_execution(self):
        adapter = self.adapter()
        self.assertEqual(adapter(CLAIM, threading.Event()), dict(kind='draft', text='Draft.'))
        payload = self.calls[1][2]
        self.assertEqual(json.loads(payload['prompt']), CLAIM)
        self.assertEqual([call[1] for call in self.calls], ['/api/tags','/api/generate','/api/tags'])
        self.assertEqual(payload['stream'], False)
        self.assertNotIn('tools', payload)
        self.assertEqual(adapter.last_run['authority_effect'], 'NONE')

    def test_missing_or_changed_pin_never_dispatches(self):
        for inventory in [dict(models=[]), dict(models=[dict(name='test:fixed',digest='c'*64)])]:
            adapter = self.adapter(); self.inventory = inventory
            with self.assertRaises(AdapterRefused): adapter(CLAIM, threading.Event())
            self.assertEqual(len(self.calls), 1)

    def test_tag_change_after_generation_refuses_output(self):
        adapter = self.adapter(); request = adapter._request
        def change(method, path, value=None):
            if path == '/api/generate': self.inventory['models'][0]['digest'] = 'c'*64
            return request(method, path, value)
        adapter._request = change
        with self.assertRaises(AdapterRefused): adapter(CLAIM, threading.Event())
        self.assertIsNone(adapter.last_run)

    def test_truncated_or_bad_output_is_not_a_completed_draft(self):
        for update in [dict(done=False),dict(done_reason='length'),dict(response=''),dict(response='\x00'),dict(model='other')]:
            adapter = self.adapter(); self.result.update(update)
            with self.subTest(update=update), self.assertRaises(AdapterRefused): adapter(CLAIM, threading.Event())

    def test_cancel_before_dispatch_never_connects(self):
        adapter=self.adapter(); cancel=threading.Event(); cancel.set()
        with self.assertRaises(AdapterRefused): adapter(CLAIM, cancel)
        self.assertEqual(self.calls, [])

    def test_late_cancel_does_not_present_output_as_success(self):
        adapter=self.adapter(); cancel=threading.Event(); request=adapter._request
        def late(method,path,value=None):
            if path=='/api/generate': cancel.set()
            return request(method,path,value)
        adapter._request=late
        with self.assertRaises(AdapterRefused): adapter(CLAIM,cancel)
        self.assertIsNone(adapter.last_run)

    def test_invalid_json_duplicate_keys_and_nonfinite_refuse(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'{']:
            with self.subTest(raw=raw),self.assertRaises(AdapterRefused): strict_json(raw)

    def test_invalid_model_pin_or_timeout_refuses(self):
        for model,pin,timeout in [('x','short',2),('x','a'*64,0),('x','a'*64,float('inf')),('',PIN,2)]:
            with self.assertRaises(AdapterRefused): OllamaDraftAdapter(model,pin,timeout=timeout)

    def test_http_error_redirect_and_size_refuse_and_close(self):
        for status,raw in [(302,b''),(500,b''),(200,b'x'*(MAX_RESPONSE_BYTES+1))]:
            with patch('ollama_adapter.http.client.HTTPConnection') as connection:
                response=connection.return_value.getresponse.return_value
                response.status=status; response.read.return_value=raw
                with self.assertRaises(AdapterRefused): OllamaDraftAdapter('x',PIN)._request('GET','/api/tags')
                connection.assert_called_once_with('127.0.0.1',11434,timeout=120)
                connection.return_value.close.assert_called_once()


if __name__=='__main__': unittest.main(verbosity=2)
