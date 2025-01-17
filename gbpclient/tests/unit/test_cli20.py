#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from unittest import mock

import fixtures
import requests

from neutronclient.common import exceptions
from neutronclient.tests.unit import test_cli20 as neutron_test_cli20

from gbpclient import gbpshell
from gbpclient.v2_0 import client as gbpclient

from six.moves import StringIO

API_VERSION = neutron_test_cli20.API_VERSION
TOKEN = neutron_test_cli20.TOKEN
ENDURL = neutron_test_cli20.ENDURL
capture_std_streams = neutron_test_cli20.capture_std_streams
end_url = neutron_test_cli20.end_url


class ParserException(Exception):
    pass


class FakeStdout(neutron_test_cli20.FakeStdout):

    pass


class MyResp(neutron_test_cli20.MyResp):

    pass


class MyApp(neutron_test_cli20.MyApp):

    pass


class MyUrlComparator(neutron_test_cli20.MyUrlComparator):

    pass


class MyComparator(neutron_test_cli20.MyComparator):

    pass


class CLITestV20Base(neutron_test_cli20.CLITestV20Base):

    shell = gbpshell
    client = gbpclient

    def setUp(self, plurals=None):
        super(CLITestV20Base, self).setUp()
        self.client = gbpclient.Client(token=TOKEN, endpoint_url=self.endurl)

    def _test_create_resource(self, resource, cmd, name, myid, args,
                              position_names, position_values,
                              tenant_id=None, tags=None, admin_state_up=True,
                              extra_body=None, cmd_resource=None,
                              parent_id=None, **kwargs):
        if not cmd_resource:
            cmd_resource = resource
        body = {resource: {}, }
        if tenant_id:
            body[resource].update({'tenant_id': tenant_id})
        if tags:
            body[resource].update({'tags': tags})
        if extra_body:
            body[resource].update(extra_body)
        body[resource].update(kwargs)

        for i in range(len(position_names)):
            body[resource].update({position_names[i]: position_values[i]})
        ress = {resource:
                {self.id_field: myid}, }
        if name:
            ress[resource].update({'name': name})
        resstr = self.client.serialize(ress)
        # url method body
        resource_plural = self.client.get_resource_plural(cmd_resource)
        path = getattr(self.client, resource_plural + "_path")
        if parent_id:
            path = path % parent_id
        mock_body = MyComparator(body, self.client)
        cmd_parser = cmd.get_parser('create_' + resource)
        resp = (MyResp(200), resstr)

        with mock.patch.object(
            cmd, "get_client", return_value=self.client
        ) as mock_get_client, mock.patch.object(
            self.client.httpclient, "request", return_value=resp
        ) as mock_request:
            gbpshell.run_command(cmd, cmd_parser, args)

            self.assert_mock_multiple_calls_with_same_arguments(
                mock_get_client, mock.call(), None)

            mock_request.assert_called_once_with(
                end_url(path), 'POST',
                body=mock_body,
                headers=neutron_test_cli20.ContainsKeyValue(
                    {'X-Auth-Token': TOKEN}))

        _str = self.fake_stdout.make_string()
        self.assertIn(myid, _str)
        if name:
            self.assertIn(name, _str)

    def check_parser_ext(self, cmd, args, verify_args, ext):
        cmd_parser = self.cmd.get_parser('check_parser')
        cmd_parser = ext.get_parser(cmd_parser)
        stderr = StringIO()
        with fixtures.MonkeyPatch('sys.stderr', stderr):
            try:
                parsed_args = cmd_parser.parse_args(args)
            except SystemExit:
                raise ParserException("Argument parse failed: %s" %
                                      stderr.getvalue())
        for av in verify_args:
            attr, value = av
            if attr:
                self.assertIn(attr, parsed_args)
                self.assertEqual(value, getattr(parsed_args, attr))
        return parsed_args


class ClientV2TestJson(CLITestV20Base):

    pass


class CLITestV20ExceptionHandler(CLITestV20Base):

    def _test_exception_handler_v20(
        self, expected_exception, status_code, expected_msg,
        error_type=None, error_msg=None, error_detail=None,
        error_content=None):
        if error_content is None:
            error_content = {'NeutronError': {'type': error_type,
                                              'message': error_msg,
                                              'detail': error_detail}}

        e = self.assertRaises(expected_exception,
                              gbpclient.exception_handler_v20,
                              status_code, error_content)
        self.assertEqual(status_code, e.status_code)

        if expected_msg is None:
            if error_detail:
                expected_msg = '\n'.join([error_msg, error_detail])
            else:
                expected_msg = error_msg
        self.assertEqual(expected_msg, e.message)

    def test_exception_handler_v20_neutron_known_error(self):
        # TODO(Sumit): This needs to be adapted for GBP
        pass

    def test_exception_handler_v20_neutron_known_error_without_detail(self):
        # TODO(Sumit): This needs to be adapted for GBP
        pass

    def test_exception_handler_v20_unknown_error_to_per_code_exception(self):
        for status_code, client_exc in list(
                exceptions.HTTP_EXCEPTION_MAP.items()):
            error_msg = 'Unknown error'
            error_detail = 'This is detail'
            self._test_exception_handler_v20(
                client_exc, status_code,
                error_msg + '\n' + error_detail,
                'UnknownError', error_msg, error_detail)

    def test_exception_handler_v20_neutron_unknown_status_code(self):
        error_msg = 'Unknown error'
        error_detail = 'This is detail'
        self._test_exception_handler_v20(
            exceptions.NeutronClientException, 501,
            error_msg + '\n' + error_detail,
            'UnknownError', error_msg, error_detail)

    def test_exception_handler_v20_bad_neutron_error(self):
        error_content = {'NeutronError': {'unknown_key': 'UNKNOWN'}}
        self._test_exception_handler_v20(
            exceptions.NeutronClientException, 500,
            expected_msg={'unknown_key': 'UNKNOWN'},
            error_content=error_content)

    def test_exception_handler_v20_error_dict_contains_message(self):
        error_content = {'message': 'This is an error message'}
        self._test_exception_handler_v20(
            exceptions.NeutronClientException, 500,
            expected_msg='This is an error message',
            error_content=error_content)

    def test_exception_handler_v20_error_dict_not_contain_message(self):
        error_content = {'error': 'This is an error message'}
        expected_msg = '%s-%s' % (500, error_content)
        self._test_exception_handler_v20(
            exceptions.NeutronClientException, 500,
            expected_msg=expected_msg,
            error_content=error_content)

    def test_exception_handler_v20_default_fallback(self):
        error_content = 'This is an error message'
        expected_msg = '%s-%s' % (500, error_content)
        self._test_exception_handler_v20(
            exceptions.NeutronClientException, 500,
            expected_msg=expected_msg,
            error_content=error_content)

    def test_exception_status(self):
        e = exceptions.BadRequest()
        self.assertEqual(e.status_code, 400)

        e = exceptions.BadRequest(status_code=499)
        self.assertEqual(e.status_code, 499)

        # SslCertificateValidationError has no explicit status_code,
        # but should have a 'safe' defined fallback.
        e = exceptions.SslCertificateValidationError()
        self.assertIsNotNone(e.status_code)

        e = exceptions.SslCertificateValidationError(status_code=599)
        self.assertEqual(e.status_code, 599)

    def test_connection_failed(self):
        self.client.httpclient.auth_token = 'token'
        excp = requests.exceptions.ConnectionError('Connection refused')

        with mock.patch.object(self.client.httpclient, "request",
                               side_effect=excp) as mock_request:
            error = self.assertRaises(exceptions.ConnectionFailed,
                                      self.client.get, '/test')

            mock_request.assert_called_once_with(
                end_url('/test'), 'GET',
                body=None,
                headers=neutron_test_cli20.ContainsKeyValue(
                    {'X-Auth-Token': 'token'}))
        # NB: ConnectionFailed has no explicit status_code, so this
        # tests that there is a fallback defined.
        self.assertIsNotNone(error.status_code)
