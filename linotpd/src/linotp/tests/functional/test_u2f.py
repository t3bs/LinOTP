# -*- coding: utf-8 -*-
#
#    LinOTP - the open source solution for two factor authentication
#    Copyright (C) 2010 - 2015 LSE Leading Security Experts GmbH
#
#    This file is part of LinOTP server.
#
#    This program is free software: you can redistribute it and/or
#    modify it under the terms of the GNU Affero General Public
#    License, version 3, as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the
#               GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#    E-mail: linotp@lsexperts.de
#    Contact: www.linotp.org
#    Support: www.lsexperts.de
#
"""
  Test the U2F token
  To test the U2F token implementation, the behavior of a U2F device is simulated
  using a demo certificate and a hard-coded key handle
"""

from linotp.tests import TestController, url
from hashlib import sha256
from M2Crypto import EC, BIO, m2
import json
import binascii
import base64
import struct
import sys
import re
import logging
log = logging.getLogger(__name__)


class TestU2FController(TestController):

    ATTESTATION_PRIVATE_KEY_PEM = \
        '-----BEGIN EC PRIVATE KEY-----\n' \
        'MHQCAQEEIBMsy03r5KbBIxkWY91FDJ7BvtTQhgPgndi282K4YrIOoAcGBSuBBAAK\n' \
        'oUQDQgAE6WAdbosEirjc9p2R17WVNzz9hbITpR90OMf/sK+1ncXMiNt06oXF/0zw\n' \
        'YnFZlka4GPRBhBtTWdgff+Ys/3JPKg==\n' \
        '-----END EC PRIVATE KEY-----'

    ATTESTATION_CERT_HEX = '30820202308201a8a003020102020900bedc78032c47968b300a06082a8648ce3d0' \
                           '40302305f310b30090603550406130244453113301106035504080c0a536f6d652d' \
                           '53746174653121301f060355040a0c18496e7465726e65742057696467697473205' \
                           '07479204c74643118301606035504030c0f4c696e4f545020553246205465737430' \
                           '1e170d3135303331383039353230315a170d3432303830333039353230315a305f3' \
                           '10b30090603550406130244453113301106035504080c0a536f6d652d5374617465' \
                           '3121301f060355040a0c18496e7465726e6574205769646769747320507479204c7' \
                           '4643118301606035504030c0f4c696e4f5450205532462054657374305630100607' \
                           '2a8648ce3d020106052b8104000a03420004e9601d6e8b048ab8dcf69d91d7b5953' \
                           '73cfd85b213a51f7438c7ffb0afb59dc5cc88db74ea85c5ff4cf06271599646b818' \
                           'f441841b5359d81f7fe62cff724f2aa350304e301d0603551d0e04160414c17d9d5' \
                           '2e8f4696d4f485353fa78e903dab72aae301f0603551d23041830168014c17d9d52' \
                           'e8f4696d4f485353fa78e903dab72aae300c0603551d13040530030101ff300a060' \
                           '82a8648ce3d0403020348003045022007e475efd0c9575e915ab89b5c8b1b436b2c' \
                           'c9a5cc4df37889e9511b1f7808f6022100c1faaa0fa5f36363962058a2e9f679338' \
                           'eca18b12725f807ffe68d1c05d3d35b'

    # Example key handle taken from the FIDO U2F specification
    KEY_HANDLE_HEX1 = '2a552dfdb7477ed65fd84133f86196010b2215b57da75d315b7b9e8fe2e3925a6019551ba' \
                      'b61d16591659cbaf00b4950f7abfe6660e2e006f76868b772d70c25'
    # Random made up key handle
    KEY_HANDLE_HEX2 = '2ae0b2f28fae6053fd697972ba7c81009137f4f46a764bc29751a28987d053ccfffb0687d' \
                      'ef306f47fd45906e838401a6437270a45a37da9c25d8db8b559a888'

    # Generate ECC key, NIST P-256 elliptic curve
    ECC_KEY1 = EC.gen_params(EC.NID_X9_62_prime256v1)
    ECC_KEY1.gen_key()

    ECC_KEY2 = EC.gen_params(EC.NID_X9_62_prime256v1)
    ECC_KEY2.gen_key()

    key_set = {1: (KEY_HANDLE_HEX1, ECC_KEY1),
               2: (KEY_HANDLE_HEX2, ECC_KEY2)
               }

    key_handle_set = {
                KEY_HANDLE_HEX1: ECC_KEY1,
                KEY_HANDLE_HEX2: ECC_KEY2,
               }

    FAKE_REGISTRATION_DATA_HEX = '0504113fafb0da1a6a90bb3a017552c1561af88bfd02c36eec334551959' \
                                 'ffe562a6f050b496545810b64b738e7673a314efd67216cc1b7c7e46f1b' \
                                 '34dcd6212a36fe402a552dfdb7477ed65fd84133f86196010b2215b57da' \
                                 '75d315b7b9e8fe2e3925a6019551bab61d16591659cbaf00b4950f7abfe' \
                                 '6660e2e006f76868b772d70c2530820202308201a8a003020102020900b' \
                                 'edc78032c47968b300a06082a8648ce3d040302305f310b300906035504' \
                                 '06130244453113301106035504080c0a536f6d652d53746174653121301' \
                                 'f060355040a0c18496e7465726e6574205769646769747320507479204c' \
                                 '74643118301606035504030c0f4c696e4f5450205532462054657374301' \
                                 'e170d3135303331383039353230315a170d343230383033303935323031' \
                                 '5a305f310b30090603550406130244453113301106035504080c0a536f6' \
                                 'd652d53746174653121301f060355040a0c18496e7465726e6574205769' \
                                 '646769747320507479204c74643118301606035504030c0f4c696e4f545' \
                                 '02055324620546573743056301006072a8648ce3d020106052b8104000a' \
                                 '03420004e9601d6e8b048ab8dcf69d91d7b595373cfd85b213a51f7438c' \
                                 '7ffb0afb59dc5cc88db74ea85c5ff4cf06271599646b818f441841b5359' \
                                 'd81f7fe62cff724f2aa350304e301d0603551d0e04160414c17d9d52e8f' \
                                 '4696d4f485353fa78e903dab72aae301f0603551d23041830168014c17d' \
                                 '9d52e8f4696d4f485353fa78e903dab72aae300c0603551d13040530030' \
                                 '101ff300a06082a8648ce3d0403020348003045022007e475efd0c9575e' \
                                 '915ab89b5c8b1b436b2cc9a5cc4df37889e9511b1f7808f6022100c1faa' \
                                 'a0fa5f36363962058a2e9f679338eca18b12725f807ffe68d1c05d3d35b' \
                                 '30440220387f2d2927e4a2bb9053b4ac09b22cc4c1bac2987e868be6f22' \
                                 '6a8f139171838022013e19c68829d52b2e5db0e80e2efb46738cc418ea9' \
                                 'ef3b94664f3817e18ddc4d'

    # set up in setUp method
    serials = None

    def setUp(self):
        self.serial = ''
        self.counter = 0
        self.origin = 'https://u2f-fakeurl.com'
        TestController.setUp(self)
        self.create_common_resolvers()
        self.create_common_realms()
        self.serials = set()

    def tearDown(self):
        for serial in self.serials:
            self.delete_token(serial)
        self.delete_all_realms()
        self.delete_all_resolvers()
        TestController.tearDown(self)

    def _registration1(self, pin=None):
        """
        Performs the first registration step
        """
        parameters = {
            'type': 'u2f',
            'phase': 'registration1',
            'user': 'root',
            'session': self.session,
            'appid': self.origin
        }
        if pin is not None:
            parameters['pin'] = pin

        response = self.app.get(url(controller='admin', action='init'),
                                params=parameters)
        return response

    def _registration2(self,
                       register_response_message,
                       pin=None
                       ):
        """
        Performs the second registration step
        """
        parameters = {
            'type': 'u2f',
            'phase': 'registration2',
            'user': 'root',
            'otpkey': register_response_message,
            'serial': self.serial,
            'session': self.session
        }
        if pin is not None:
            parameters['pin'] = pin

        response = self.app.get(url(controller='admin', action='init'),
                                params=parameters)
        return response

    def _authentication1(self, pin=None):
        """
        Performs the initial authentication step
        """
        parameters = {
            'user': 'root',
            'pass': ''
        }
        if pin is not None:
            parameters['pass'] = pin

        response = self.app.get(url(controller='validate', action='check'),
                                params=parameters)
        return response

    def _authentication2(self,
                         transactionid,
                         authentication_response_message
                         ):
        """
        Performs the second authentication step
        """
        parameters = {
            'user': 'root',
            'transactionid': transactionid
        }

        parameters['pass'] = authentication_response_message

        response = self.app.get(url(controller='validate', action='check'),
                                params=parameters)

        return response

    def _createClientDataObject(self, typ, challenge):
        """
        Creates a client data object of the type 'registration' or 'authentication'
        """
        typ_string = ''
        if typ == 'registration':
            typ_string = 'navigator.id.finishEnrollment'
        elif typ == 'authentication':
            typ_string = 'navigator.id.getAssertion'
        else:
            raise ValueError('Unknown typ')

        client_data_object = {
            'typ': typ_string,
            'challenge': challenge,
            'origin': self.origin
        }
        client_data_object_JSON = json.dumps(client_data_object)
        return client_data_object_JSON

    def _createRegistrationResponseMessage(self,
                                           client_data,
                                           key_set=None,
                                           correct=True
                                           ):
        """
        Create a registration response message according to the FIDO U2F specification
        """
        if not key_set:
            raise ValueError("Unknown key number requested!")
        (key_handle_hex, ecc_key) = key_set

        #
        # Create the registration_data object
        #
        registration_data = chr(0x05)  # First byte must be 0x05

        # The public key length is set to a fixed length of 65 characters in the U2F specification
        public_key = str(ecc_key.pub().get_der())[-65:]
        registration_data += public_key

        key_handle = binascii.unhexlify(key_handle_hex)
        registration_data += chr(len(key_handle))
        registration_data += key_handle

        attestation_cert_der = binascii.unhexlify(self.ATTESTATION_CERT_HEX)
        registration_data += attestation_cert_der

        # Create the ECDSA signature
        digest = sha256()
        digest.update(chr(0x00) +
                      sha256(self.origin).digest() +
                      sha256(client_data).digest() +
                      key_handle +
                      public_key
                      )

        cert_private_key = EC.load_key_bio(BIO.MemoryBuffer(self.ATTESTATION_PRIVATE_KEY_PEM))
        signature = cert_private_key.sign_dsa_asn1(digest.digest())

        if correct is False:
            # Change the signature to create an invalid registration response
            signature = signature[:-1]

        registration_data += signature

        #
        # Create the registration_response
        #
        registration_response = {
            'registrationData': base64.urlsafe_b64encode(registration_data),
            'clientData': base64.urlsafe_b64encode(client_data)
        }

        return json.dumps(registration_response)

    def _createAuthenticationResponseMessage(self,
                                             client_data,
                                             key_handle,
                                             ecc_key=None,
                                             correct=True
                                             ):
        """
        Create an authentication response message according to the FIDO U2F specification
        """
        # get the correct token for creating the response message
        if not ecc_key:
            raise ValueError("Unknown key handle received.")

        #
        # Create the signatureData object
        #
        authentication_data = chr(0x01)  # User presence byte

        # counter
        self.counter += 1
        authentication_data += struct.pack('>I', self.counter)

        # signature
        digest = sha256()
        digest.update(sha256(self.origin).digest() +
                      chr(0x01) +
                      struct.pack('>I', self.counter) +
                      sha256(client_data).digest()
                      )
        signature = ecc_key.sign_dsa_asn1(digest.digest())

        if correct is False:
            # Change the signature to create an invalid authentication response
            signature = signature[:-1]

        authentication_data += signature

        #
        # Create the signResponse object
        #
        key_handle_index = 1
        # Remove trailing '=' characters
        while key_handle[-key_handle_index] == '=':
            key_handle_index = key_handle_index + 1
        if key_handle_index > 1:
            key_handle = key_handle[:-(key_handle_index - 1)]
        sign_response = {
            'keyHandle': key_handle,
            'signatureData': base64.urlsafe_b64encode(authentication_data),
            'clientData': base64.urlsafe_b64encode(client_data)
        }

        return json.dumps(sign_response)

    def _registration(self, pin=None, correct=True, key_num=1):
        """
        Enroll a U2F token with given token pin
        """
        # Initial token registration step
        response_registration1_JSON = self._registration1(pin)
        self.assertIn('"value": true', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"registerrequest":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"challenge":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"version":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"appId":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"serial":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)

        response_registration1 = json.loads(response_registration1_JSON.body)
        challenge_registration = response_registration1.get('detail', {})\
                                                       .get('registerrequest', {})\
                                                       .get('challenge')
        self.serial = response_registration1.get('detail', {}).get('serial')
        self.serials.add(self.serial)

        # Construct the registration response message
        client_data_registration = self._createClientDataObject('registration',
                                                                challenge_registration,
                                                                )

        key_set = self.key_set.get(key_num, None)

        registration_response_message = \
            self._createRegistrationResponseMessage(client_data_registration,
                                                    correct=correct,
                                                    key_set=key_set
                                                    )

        # Complete the token registration
        response_registration2_JSON = self._registration2(registration_response_message, pin)
        if correct is True:
            # Registration should be successful
            self.assertTrue('"value": true' in response_registration2_JSON,
                            "Response: %r" % response_registration2_JSON)
        else:
            # Registration should have failed
            self.assertTrue('"status": false' in response_registration2_JSON,
                            "Response: %r" % response_registration2_JSON)

        return

    def _authentication_challenge(self, pin=None):
        """
        Test authentication of a previously registered token with given token pin
        """
        # Initial authentication phase
        response_authentication1_JSON = self._authentication1(pin)
        self.assertIn('"value": false', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"transactionid":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"signrequest":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"challenge":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"version":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"appId":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"keyHandle":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)
        self.assertIn('"message":', response_authentication1_JSON,
                        "Response: %r" % response_authentication1_JSON)

        response_authentication1 = json.loads(response_authentication1_JSON.body)
        message_authentication_JSON = response_authentication1.get('detail', {}).get('message')

        reply = []
        if message_authentication_JSON == "Multiple challenges submitted.":
            challenges = response_authentication1.get('detail', {})\
                                                 .get('challenges', {})
            reply.extend(challenges.values())
        else:
            reply.append(response_authentication1.get('detail'))
        return reply

    def _authentication_response(self, challenge, correct=True):
        signrequest_authentication = challenge.get('signrequest', {})
        challenge_authentication = signrequest_authentication.get('challenge', '')

        # Does the received keyHandle match the sent one?
        key_handle_authentication = signrequest_authentication.get('keyHandle', '')
        transactionid_authentication = challenge.get('transactionid')
        # Correct the padding
        key_handle_authentication = \
            key_handle_authentication + ('=' * (4 - (len(key_handle_authentication) % 4)))
        key_handle_authentication = key_handle_authentication.encode('ascii')
        self.assertTrue(binascii.hexlify(base64.urlsafe_b64decode(key_handle_authentication)) in \
                        [self.KEY_HANDLE_HEX1, self.KEY_HANDLE_HEX2],
                        "signrequest: %r" % signrequest_authentication
                        )

        # Construct the registration response message
        client_data_authentication = self._createClientDataObject('authentication',
                                                                  challenge_authentication,
                                                                  )

        key_handle_hex = binascii.hexlify(base64.urlsafe_b64decode(key_handle_authentication))
        ecc_key = self.key_handle_set.get(key_handle_hex, None)

        authentication_response_message = \
            self._createAuthenticationResponseMessage(client_data_authentication,
                                                      key_handle_authentication,
                                                      ecc_key=ecc_key,
                                                      correct=correct
                                                      )
        # Complete the token authentication
        response_authentication2_JSON = self._authentication2(transactionid_authentication,
                                                              authentication_response_message,
                                                              )
        if correct is True:
            # Authentication should be successful
            self.assertTrue('"value": true' in response_authentication2_JSON,
                            "Response: %r" % response_authentication2_JSON)
        else:
            # Authentication should have failed
            self.assertTrue('"value": false' in response_authentication2_JSON,
                            "Response: %r" % response_authentication2_JSON)

    def _has_EC_support(self):
        has_ec_support = True
        # U2F needs OpenSSL 1.0.0 or higher
        # The EC OpenSSL API calls made by M2Crypto don't work with OpenSSl 0.9.8!
        version_text = m2.OPENSSL_VERSION_TEXT
        match = re.match(r"OpenSSL (?P<version>\d\.\d\.\d)", version_text)
        if match is None:
            # Fail on unknown OpenSSL version string format
            self.fail("Could not detect OpenSSL version - unknown version string format: '%s'"
                      % version_text)
        else:
            if match.group('version')[0] == '0':
                has_ec_support = False

        # The following command needs support for ECDSA in openssl!
        # Since Red Hat systems (including Fedora) use an openssl version without
        # support for the NIST P-256 elliptic curve (as of March 2015),
        # this command will fail with a NULL pointer exception on these systems
        try:
            EC.load_key_bio(BIO.MemoryBuffer(self.ATTESTATION_PRIVATE_KEY_PEM))
        except ValueError:
            has_ec_support = False

        return has_ec_support

    def test_u2f_registration_and_authentication_without_pin(self):
        """
        Enroll a U2F token without a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        self._registration()
        # Authenticate twice
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[0])
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[0])
        return

    def test_u2f_multiple_registration_and_authentication_without_pin(self):
        """
        Enroll a U2F token without a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        self._registration(key_num=1)
        self._registration(key_num=2)

        # Try authenticating twice with each token
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[1])
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[1])
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[0])
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[0])
        return

    def test_u2f_registration_and_wrong_authentication_without_pin(self):
        """
        Enroll a U2F token without a token pin and perform an invalid authentication
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        self._registration()
        # Authenticate twice
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[0], correct=False)
        return

    def test_u2f_multiple_registration_and_wrong_authentication_without_pin(self):
        """
        Enroll a U2F token without a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        self._registration(key_num=1)
        self._registration(key_num=2)

        # Try authenticating twice with each token
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[0], correct=False)
        challenges = self._authentication_challenge()
        self._authentication_response(challenges[1], correct=False)
        return

    def test_u2f_wrong_registration_without_pin(self):
        """
        Try an invalid registration of a U2F token without pin
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        self._registration(correct=False)
        return

    def test_u2f_registration_and_authentication_with_pin(self):
        """
        Enroll a U2F token with a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        pin = 'test{pass}word_with{curly-braces{'
        self._registration(pin)
        # Authenticate twice
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[0])
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[0])
        return

    def test_u2f_multiple_registration_and_authentication_with_pin(self):
        """
        Enroll a U2F token without a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        pin = 'test{pass}word_with{curly-braces{'
        self._registration(pin=pin, key_num=1)
        self._registration(pin=pin, key_num=2)

        # Try authenticating twice with each token
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[1])
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[1])
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[0])
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[0])
        return

    def test_u2f_registration_and_wrong_authentication_with_pin(self):
        """
        Enroll a U2F token with a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        pin = 'test{pass}word_with{curly-braces{'
        self._registration(pin)
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[0], correct=False)
        return

    def test_u2f_multiple_registration_and_wrong_authentication_with_pin(self):
        """
        Enroll a U2F token without a token pin and authenticate
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        pin = 'test{pass}word_with{curly-braces{'
        self._registration(pin=pin, key_num=1)
        self._registration(pin=pin, key_num=2)

        # Try authenticating twice with each token
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[0], correct=False)
        challenges = self._authentication_challenge(pin)
        self._authentication_response(challenges[1], correct=False)
        return

    def test_u2f_wrong_registration_with_pin(self):
        """
        Try an invalid registration of a U2F token with pin
        """
        if not self._has_EC_support():
            self.skipTest(
                "Probably no OpenSSL support for the needed NIST P-256 curve!"
                )
        pin = 'test{pass}word_with{curly-braces{'
        self._registration(pin=pin, correct=False)
        return

    def test_u2f_unsupported_openssl_version(self):
        """
        Try a registration with an unsupported OpenSSL version and check the error messages
        """
        version_text = m2.OPENSSL_VERSION_TEXT
        match = re.match(r"OpenSSL (?P<version>\d\.\d\.\d)", version_text)
        if match is None:
            # Fail on unknown OpenSSL version string format
            self.fail("Could not detect OpenSSL version - unknown version string format: '%s'"
                      % version_text)
        else:
            if match.group('version')[0] != '0':
                # Supported OpenSSL version - skip test
                self.skipTest(
                    "This test can only be run with an unsupported OpenSSL "
                    "version!"
                    )

        # Initial token registration step
        response_registration1_JSON = self._registration1()
        self.assertIn('"value": true', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"registerrequest":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"challenge":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"version":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"appId":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"serial":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)

        response_registration1 = json.loads(response_registration1_JSON.body)
        challenge_registration = response_registration1.get('detail', {})\
                                                       .get('registerrequest', {})\
                                                       .get('challenge')
        self.serial = response_registration1.get('detail', {}).get('serial')
        self.serials.add(self.serial)

        client_data_registration = self._createClientDataObject('registration',
                                                                challenge_registration,
                                                                )
        # Since we have no supported OpenSSL version to calculate the registration response
        # we use a hard-coded correctly-formed fake registration response
        registration_response = binascii.unhexlify(self.FAKE_REGISTRATION_DATA_HEX)
        registration_response_message = {
            'registrationData': base64.urlsafe_b64encode(registration_response),
            'clientData': base64.urlsafe_b64encode(client_data_registration)
        }

        # Complete the token registration
        response_registration2_JSON = \
            self._registration2(json.dumps(registration_response_message))

        # Registration must fail
        self.assertTrue('"status": false'in response_registration2_JSON,
                        "Response: %r" % response_registration2_JSON)

        # Check for correct error messages
        self.assertTrue('"message": "This version of OpenSSL is not supported!' in
                        response_registration2_JSON,
                        "Response: %r" % response_registration2_JSON
                        )

    def test_u2f_unsupported_openssl_missing_curve(self):
        """
        Try registration with an OpenSSL missing the NIST P-256 curve and check the error messages
        """
        skip_test = True

        # Only allow OpenSSL >=1.0.0 with missing EC support
        version_text = m2.OPENSSL_VERSION_TEXT
        match = re.match(r"OpenSSL (?P<version>\d\.\d\.\d)", version_text)
        if match is None:
            # Fail on unknown OpenSSL version string format
            self.fail("Could not detect OpenSSL version - unknown version string format: '%s'"
                      % version_text)
        else:
            if match.group('version')[0] != '0':
                # Only run test on missing NIST P-256 curve support
                try:
                    EC.load_key_bio(BIO.MemoryBuffer(self.ATTESTATION_PRIVATE_KEY_PEM))
                except ValueError:
                    skip_test = False

        if skip_test:
            self.skipTest(
                "This test can only be run with OpenSSL missing the "
                "NIST P-256 curve!"
                )

        # Initial token registration step
        response_registration1_JSON = self._registration1()
        self.assertIn('"value": true', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"registerrequest":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"challenge":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"version":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"appId":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)
        self.assertIn('"serial":', response_registration1_JSON,
                        "Response: %r" % response_registration1_JSON)

        response_registration1 = json.loads(response_registration1_JSON.body)
        challenge_registration = response_registration1.get('detail', {}).get('challenge')
        self.serial = response_registration1.get('detail', {}).get('serial')
        self.serials.add(self.serial)

        client_data_registration = self._createClientDataObject('registration',
                                                                challenge_registration,
                                                                )
        # Since we have no supported OpenSSL version to calculate the registration response
        # we use a hard-coded correctly-formed fake registration response
        registration_response = binascii.unhexlify(self.FAKE_REGISTRATION_DATA_HEX)
        registration_response_message = {
            'registrationData': base64.urlsafe_b64encode(registration_response),
            'clientData': base64.urlsafe_b64encode(client_data_registration)
        }

        # Complete the token registration
        response_registration2_JSON = \
            self._registration2(json.dumps(registration_response_message))

        # Registration must fail
        self.assertTrue('"status": false'in response_registration2_JSON,
                        "Response: %r" % response_registration2_JSON)

        # Check for correct error messages
        self.assertTrue('missing ECDSA support for the NIST P-256 curve in OpenSSL' in
                        response_registration2_JSON,
                        "Response: %r" % response_registration2_JSON
                        )