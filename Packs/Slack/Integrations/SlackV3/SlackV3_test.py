import json as js
import threading
import io

import pytest
import slack_sdk
from slack_sdk.web.slack_response import SlackResponse
from slack_sdk.errors import SlackApiError

from unittest.mock import MagicMock

from CommonServerPython import *

import datetime


def load_test_data(path):
    with io.open(path, mode='r', encoding='utf-8') as f:
        return f.read()


USERS = load_test_data('./test_data/users.txt')
CONVERSATIONS = load_test_data('./test_data/conversations.txt')
PAYLOAD_JSON = load_test_data('./test_data/payload.txt')

BOT = '''{
    "ok": true,
    "url": "https://subarachnoid.slack.com/",
    "team": "Subarachnoid Workspace",
    "user": "grace",
    "team_id": "T12345678",
    "user_id": "W12345678"
}'''

MIRRORS = '''
   [{
     "channel_id":"GKQ86DVPH",
     "channel_name": "incident-681",
     "channel_topic": "incident-681",
     "investigation_id":"681",
     "mirror_type":"all",
     "mirror_direction":"both",
     "mirror_to":"group",
     "auto_close":true,
     "mirrored":true
  },
  {
     "channel_id":"GKB19PA3V",
     "channel_name": "group2",
     "channel_topic": "cooltopic",
     "investigation_id":"684",
     "mirror_type":"all",
     "mirror_direction":"both",
     "mirror_to":"group",
     "auto_close":true,
     "mirrored":true
  },
  {
     "channel_id":"GKB19PA3V",
     "channel_name": "group2",
     "channel_topic": "cooltopic",
     "investigation_id":"692",
     "mirror_type":"all",
     "mirror_direction":"both",
     "mirror_to":"group",
     "auto_close":true,
     "mirrored":true
  },
  {
     "channel_id":"GKNEJU4P9",
     "channel_name": "group3",
     "channel_topic": "incident-713",
     "investigation_id":"713",
     "mirror_type":"all",
     "mirror_direction":"both",
     "mirror_to":"group",
     "auto_close":true,
     "mirrored":true
  },
  {
     "channel_id":"GL8GHC0LV",
     "channel_name": "group5",
     "channel_topic": "incident-734",
     "investigation_id":"734",
     "mirror_type":"all",
     "mirror_direction":"both",
     "mirror_to":"group",
     "auto_close":true,
     "mirrored":true
  }]
'''

BLOCK_JSON = [{
    'type': 'section',
    'text': {
        'type': 'mrkdwn',
        'text': 'text'
    }
}, {
    'type': 'actions',
    'elements': [{
        'type': 'button',
        'text': {
            'type': 'plain_text',
            'emoji': True,
            'text': 'yes'
        },
        'style': 'primary',
        'value': '{\"entitlement\": \"e95cb5a1-e394-4bc5-8ce0-508973aaf298@22|43\", \"reply\": \"Thanks bro\"}',
    }, {
        'type': 'button',
        'text': {
            'type': 'plain_text',
            'emoji': True,
            'text': 'no'
        },
        'style': 'danger',
        'value': '{\"entitlement\": \"e95cb5a1-e394-4bc5-8ce0-508973aaf298@22|43\", \"reply\": \"Thanks bro\"}',
    }]}]

SLACK_RESPONSE = SlackResponse(client=None, http_verb='', api_url='', req_args={}, data={'ts': 'cool'}, headers={},
                               status_code=0)
SLACK_RESPONSE_2 = SlackResponse(client=None, http_verb='', api_url='', req_args={}, data={'cool': 'cool'}, headers={},
                                 status_code=0)


def test_exception_in_invite_to_mirrored_channel(mocker):
    import SlackV3
    from SlackV3 import check_for_mirrors
    new_user = {
        'name': 'perikles',
        'profile': {
            'email': 'perikles@acropoli.com',
        },
        'id': 'U012B3CUI'
    }

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        users = {'members': js.loads(USERS)}
        users['members'].append(new_user)
        return users

    # Set
    mirrors = js.loads(MIRRORS)
    mirrors.append({
        'channel_id': 'new_group',
        'channel_name': 'channel',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    })

    set_integration_context({
        'mirrors': js.dumps(mirrors),
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'mirrorInvestigation', return_value=[{'email': 'spengler@ghostbusters.example.com',
                                                                       'username': 'spengler'},
                                                                      {'email': 'perikles@acropoli.com',
                                                                       'username': 'perikles'}])
    mocker.patch.object(SlackV3, 'invite_to_mirrored_channel', side_effect=Exception)
    mocker.patch.object(demisto, 'error')
    check_for_mirrors()
    assert demisto.setIntegrationContext.call_count != 0
    assert demisto.error.call_args[0][0] == 'Could not invite investigation users to the mirrored channel: '


def get_integration_context():
    return INTEGRATION_CONTEXT


def set_integration_context(integration_context):
    global INTEGRATION_CONTEXT
    INTEGRATION_CONTEXT = integration_context


RETURN_ERROR_TARGET = 'SlackV3.return_error'


@pytest.fixture(autouse=True)
def setup(mocker):
    import SlackV3

    mocker.patch.object(demisto, 'info')
    mocker.patch.object(demisto, 'debug')

    set_integration_context({
        'mirrors': MIRRORS,
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    SlackV3.init_globals()
    # We will manually change the caching mode to ensure it doesn't break previous user's envs.
    SlackV3.ENABLE_CACHING = False


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


@pytest.mark.asyncio
async def test_get_slack_name_user(mocker):
    from SlackV3 import get_slack_name

    async def users_info(user: str):
        if user != 'alexios':
            return js.loads(USERS)[0]
        return None

    async def conversations_info():
        return {'channel': js.loads(CONVERSATIONS)[0]}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext')

    #
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'users_info', side_effect=users_info)
    mocker.patch.object(socket_client, 'conversations_info', side_effect=conversations_info)
    # Assert 6516

    # User in integration context
    user_id = 'U012A3CDE'
    name = await get_slack_name(user_id, socket_client)
    assert name == 'spengler'
    assert socket_client.call_count == 0

    # User not in integration context
    unknown_user = 'USASSON'
    name = await get_slack_name(unknown_user, socket_client)
    assert name == 'spengler'
    assert socket_client.users_info.call_count == 1

    # User does not exist
    nonexisting_user = 'alexios'
    name = await get_slack_name(nonexisting_user, socket_client)
    assert name == ''
    assert socket_client.users_info.call_count == 1


@pytest.mark.asyncio
async def test_get_slack_name_channel(mocker):
    from SlackV3 import get_slack_name

    # Set

    async def users_info(user: str):
        if user != 'alexios':
            return js.loads(USERS)[0]
        return None

    async def conversations_info(channel=''):
        return js.loads(CONVERSATIONS)[0]

    socket_client = AsyncMock()

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext')
    mocker.patch.object(socket_client, 'users_info', side_effect=users_info)
    mocker.patch.object(socket_client, 'conversations_info',
                        side_effect=conversations_info)

    # Assert

    # Channel in integration context
    channel_id = 'C012AB3CD'
    name = await get_slack_name(channel_id, socket_client)
    assert name == 'general'
    assert socket_client.api_call.call_count == 0

    # Channel not in integration context
    unknown_channel = 'CSASSON'
    name = await get_slack_name(unknown_channel, socket_client)
    assert name == 'general'
    assert socket_client.conversations_info.call_count == 1

    # Channel doesn't exist
    nonexisting_channel = 'lulz'
    name = await get_slack_name(nonexisting_channel, socket_client)
    assert name == ''
    assert socket_client.conversations_info.call_count == 1


@pytest.mark.asyncio
async def test_clean_message(mocker):
    from SlackV3 import clean_message

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.info':
            return {'user': js.loads(USERS)[0]}
        elif method == 'conversations.info':
            return {'channel': js.loads(CONVERSATIONS)[0]}
        return None

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    user_message = 'Hello <@U012A3CDE>!'
    channel_message = 'Check <#C012AB3CD>'
    link_message = 'Go to <https://www.google.com/lulz>'

    # Arrange

    clean_user_message = await clean_message(user_message, slack_sdk.WebClient)
    clean_channel_message = await clean_message(channel_message, slack_sdk.WebClient)
    clean_link_message = await clean_message(link_message, slack_sdk.WebClient)

    # Assert

    assert clean_user_message == 'Hello spengler!'
    assert clean_channel_message == 'Check general'
    assert clean_link_message == 'Go to https://www.google.com/lulz'


class TestGetConversationByName:
    @staticmethod
    def set_conversation_mock(mocker, get_context=get_integration_context):
        mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_context)
        mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
        mocker.patch.object(slack_sdk.WebClient, 'api_call', return_value={'channels': js.loads(CONVERSATIONS)})

    def test_get_conversation_by_name_exists_in_context(self, mocker):
        """
        Given:
        - Conversation to find

        When:
        - Conversation exists in context

        Then:
        - Check if the right conversation returned
        - Check that no API command was called.
        """
        from SlackV3 import get_conversation_by_name
        self.set_conversation_mock(mocker)

        conversation_name = 'general'
        conversation = get_conversation_by_name(conversation_name)

        # Assertions
        assert conversation_name == conversation['name']
        assert slack_sdk.WebClient.api_call.call_count == 0

    def test_get_conversation_by_name_exists_in_api_call(self, mocker):
        """
        Given:
        - Conversation to find

        When:
        - Conversation not exists in context, but do in the API

        Then:
        - Check if the right conversation returned
        - Check that a API command was called.
        """

        def get_context():
            return {}

        from SlackV3 import get_conversation_by_name

        self.set_conversation_mock(mocker, get_context=get_context)

        conversation_name = 'general'
        conversation = get_conversation_by_name(conversation_name)

        # Assertions
        assert conversation_name == conversation['name']
        assert slack_sdk.WebClient.api_call.call_count == 1

        # Find that 'general' conversation has been added to context
        conversations = json.loads(demisto.setIntegrationContext.call_args[0][0]['conversations'])
        filtered = list(filter(lambda c: c['name'] == conversation_name, conversations))
        assert filtered, 'Could not find the \'general\' conversation in the context'

    def test_get_conversation_by_name_not_exists(self, mocker):
        """
        Given:
        - Conversation to find

        When:
        - Conversation do not exists.

        Then:
        - Check no conversation was returned.
        - Check that a API command was called.
        """
        from SlackV3 import get_conversation_by_name
        self.set_conversation_mock(mocker)

        conversation_name = 'no exists'
        conversation = get_conversation_by_name(conversation_name)
        assert not conversation
        assert slack_sdk.WebClient.api_call.call_count == 1


def test_get_user_by_name(mocker):
    from SlackV3 import get_user_by_name
    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        new_user = {
            'name': 'perikles',
            'profile': {
                'email': 'perikles@acropoli.com',
                'display_name': 'Dingus',
                'real_name': 'Lingus'
            },
            'id': 'U012B3CUI'
        }
        if method == 'users.list':
            users = {'members': js.loads(USERS)}
            users['members'].append(new_user)
            return users
        elif method == 'users.lookupByEmail':
            return {'user': new_user}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    # Assert
    # User name exists in integration context
    username = 'spengler'
    user = get_user_by_name(username)
    assert user['id'] == 'U012A3CDE'
    assert slack_sdk.WebClient.api_call.call_count == 0

    # User email exists in integration context
    email = 'spengler@ghostbusters.example.com'
    user = get_user_by_name(email)
    assert user['id'] == 'U012A3CDE'
    assert slack_sdk.WebClient.api_call.call_count == 0

    # User name doesn't exist in integration context
    username = 'perikles'
    user = get_user_by_name(username)
    assert user['id'] == 'U012B3CUI'
    assert slack_sdk.WebClient.api_call.call_count == 1

    set_integration_context({
        'mirrors': MIRRORS,
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    # User email doesn't exist in integration context
    email = 'perikles@acropoli.com'
    user = get_user_by_name(email)
    assert user['id'] == 'U012B3CUI'
    assert slack_sdk.WebClient.api_call.call_count == 2

    # User doesn't exist
    username = 'alexios'
    user = get_user_by_name(username)
    assert user == {}
    assert slack_sdk.WebClient.api_call.call_count == 3


def test_get_user_by_name_caching_disabled(mocker):
    """
    Given:
        Test Case 1 - User's name only
        Test Case 2 - A user's valid email
        Test Case 3 - A user's valid email which is not in Slack.
    When:
        Searching for a user's ID
    Then:
        Test Case 1 - Assert that only an empty dict was returned and the API was not called.
        Test Case 2 - Assert That the user's ID was found in the returned dict.
        Test Case 3 - Assert that only an empty dict was returned
    """
    import SlackV3
    # Set

    user_1 = {'user': js.loads(USERS)[0]}
    user_2 = {'user': {}}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=[user_1, user_2])

    SlackV3.DISABLE_CACHING = True
    # Assert
    # User name exists in integration context
    username = 'spengler'
    user = SlackV3.get_user_by_name(username)
    assert user == {}
    assert slack_sdk.WebClient.api_call.call_count == 0

    # User email exists in Slack API
    email = 'spengler@ghostbusters.example.com'
    user = SlackV3.get_user_by_name(email)
    assert user['id'] == 'U012A3CDE'
    assert slack_sdk.WebClient.api_call.call_count == 1

    # User email doesn't exist in Slack API
    email = 'perikles@acropoli.com'
    user = SlackV3.get_user_by_name(email)
    assert user == {}
    assert slack_sdk.WebClient.api_call.call_count == 2


def test_get_user_by_name_paging(mocker):
    from SlackV3 import get_user_by_name
    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if len(params) == 1:
            return {'members': js.loads(USERS), 'response_metadata': {
                'next_cursor': 'dGVhbTpDQ0M3UENUTks='
            }}
        else:
            return {'members': [{
                'id': 'U248918AB',
                'name': 'alexios'
            }], 'response_metadata': {
                'next_cursor': ''
            }}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    # Arrange
    user = get_user_by_name('alexios')
    args = slack_sdk.WebClient.api_call.call_args_list
    first_args = args[0][1]
    second_args = args[1][1]

    # Assert
    assert len(first_args['params']) == 1
    assert first_args['params']['limit'] == 200
    assert len(second_args['params']) == 2
    assert second_args['params']['cursor'] == 'dGVhbTpDQ0M3UENUTks='
    assert user['id'] == 'U248918AB'
    assert slack_sdk.WebClient.api_call.call_count == 2


def test_mirror_investigation_new_mirror(mocker):
    from SlackV3 import mirror_investigation

    # Set
    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        if method == 'conversations.create':
            if 'is_private' not in json:
                return {'channel': {
                    'id': 'new_channel', 'name': 'incident-999'
                }}
            return {'channel': {
                'id': 'new_group', 'name': 'incident-999'
            }}
        else:
            return {}

    mocker.patch.object(demisto, 'args', return_value={})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '999', 'users': ['spengler', 'alexios']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'demistoUrls', return_value={'server': 'https://www.eizelulz.com:8443'})
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'new_group',
        'channel_name': 'incident-999',
        'channel_topic': 'incident-999',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    }
    # Arrange

    mirror_investigation()
    success_results = demisto.results.call_args_list[0][0]

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    new_conversations = js.loads(new_context['conversations'])
    our_conversation_filter = list(filter(lambda c: c['id'] == 'new_group', new_conversations))
    our_conversation = our_conversation_filter[0]
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    # Assert

    calls = slack_sdk.WebClient.api_call.call_args_list

    groups_call = [c for c in calls if c[0][0] == 'conversations.create']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']
    chat_call = [c for c in calls if c[0][0] == 'chat.postMessage']

    message_args = chat_call[0][1]['json']

    assert len(groups_call) == 1
    assert len(invite_call) == 1
    assert len(topic_call) == 1
    assert len(chat_call) == 1

    assert success_results[0] == 'Investigation mirrored successfully, channel: incident-999'
    assert message_args['channel'] == 'new_group'
    assert message_args['text'] == 'This channel was created to mirror incident 999.' \
                                   ' \n View it on: https://www.eizelulz.com:8443#/WarRoom/999'

    assert len(our_conversation_filter) == 1
    assert len(our_mirror_filter) == 1
    assert our_conversation == {'id': 'new_group', 'name': 'incident-999'}
    assert our_mirror == new_mirror


def test_mirror_investigation_new_mirror_with_name(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        if method == 'conversations.create':
            if 'is_private' not in json:
                return {'channel': {
                    'id': 'new_channel', 'name': 'coolname'
                }}
            return {'channel': {
                'id': 'new_group', 'name': 'coolname'
            }}
        else:
            return {}

    mocker.patch.object(demisto, 'args', return_value={'channelName': 'coolname'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '999', 'users': ['spengler', 'alexios']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'demistoUrls', return_value={'server': 'https://www.eizelulz.com:8443'})
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'new_group',
        'channel_name': 'coolname',
        'channel_topic': 'incident-999',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    }
    # Arrange

    mirror_investigation()
    success_results = demisto.results.call_args_list[0][0]

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    new_conversations = js.loads(new_context['conversations'])
    our_conversation_filter = list(filter(lambda c: c['id'] == 'new_group', new_conversations))
    our_conversation = our_conversation_filter[0]
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    # Assert

    calls = slack_sdk.WebClient.api_call.call_args_list

    groups_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']
    chat_call = [c for c in calls if c[0][0] == 'chat.postMessage']

    message_args = chat_call[0][1]['json']

    assert len(groups_call) == 1
    assert len(users_call) == 0
    assert len(invite_call) == 1
    assert len(topic_call) == 1
    assert len(chat_call) == 1

    assert success_results[0] == 'Investigation mirrored successfully, channel: coolname'
    assert message_args['channel'] == 'new_group'
    assert message_args['text'] == 'This channel was created to mirror incident 999.' \
                                   ' \n View it on: https://www.eizelulz.com:8443#/WarRoom/999'

    assert len(our_conversation_filter) == 1
    assert len(our_mirror_filter) == 1
    assert our_conversation == {'id': 'new_group', 'name': 'coolname'}
    assert our_mirror == new_mirror


def test_mirror_investigation_new_mirror_with_topic(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        if method == 'conversations.create':
            if 'is_private' not in json:
                return {'channel': {
                    'id': 'new_channel', 'name': 'coolname'
                }}
            return {'channel': {
                'id': 'new_group', 'name': 'coolname'
            }}
        else:
            return {}

    mocker.patch.object(demisto, 'args', return_value={'channelName': 'coolname', 'channelTopic': 'cooltopic'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '999', 'users': ['spengler', 'alexios']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'demistoUrls', return_value={'server': 'https://www.eizelulz.com:8443'})
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'new_group',
        'channel_name': 'coolname',
        'channel_topic': 'cooltopic',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    }
    # Arrange

    mirror_investigation()

    success_results = demisto.results.call_args_list[0][0]
    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    new_conversations = js.loads(new_context['conversations'])
    our_conversation_filter = list(filter(lambda c: c['id'] == 'new_group', new_conversations))
    our_conversation = our_conversation_filter[0]
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    calls = slack_sdk.WebClient.api_call.call_args_list
    groups_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']
    chat_call = [c for c in calls if c[0][0] == 'chat.postMessage']

    message_args = chat_call[0][1]['json']
    topic_args = topic_call[0][1]['json']

    # Assert

    assert len(groups_call) == 1
    assert len(users_call) == 0
    assert len(invite_call) == 1
    assert len(topic_call) == 1
    assert len(chat_call) == 1

    assert success_results[0] == 'Investigation mirrored successfully, channel: coolname'
    assert message_args['channel'] == 'new_group'
    assert message_args['text'] == 'This channel was created to mirror incident 999.' \
                                   ' \n View it on: https://www.eizelulz.com:8443#/WarRoom/999'

    assert topic_args['channel'] == 'new_group'
    assert topic_args['topic'] == 'cooltopic'
    assert len(our_conversation_filter) == 1
    assert len(our_mirror_filter) == 1
    assert our_conversation == {'id': 'new_group', 'name': 'coolname'}
    assert our_mirror == new_mirror


def test_mirror_investigation_existing_mirror_error_type(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}

    mocker.patch.object(demisto, 'args', return_value={'type': 'chat', 'autoclose': 'false',
                                                       'direction': 'FromDemisto', 'mirrorTo': 'channel'})
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681', 'users': ['spengler']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    # Arrange
    with pytest.raises(InterruptedError):
        mirror_investigation()

    err_msg = return_error_mock.call_args[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list
    channels_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']

    # Assert
    assert len(topic_call) == 0
    assert len(users_call) == 0
    assert len(invite_call) == 0
    assert len(channels_call) == 0

    assert return_error_mock.call_count == 1
    assert err_msg == 'Cannot change the Slack channel type from XSOAR.'


def test_mirror_investigation_existing_mirror_error_name(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}

    mocker.patch.object(demisto, 'args', return_value={'channelName': 'eyy'})
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681', 'users': ['spengler']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    # Arrange

    with pytest.raises(InterruptedError):
        mirror_investigation()

    err_msg = return_error_mock.call_args[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list
    channels_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']

    # Assert
    assert len(invite_call) == 0
    assert len(channels_call) == 0
    assert len(users_call) == 0

    assert return_error_mock.call_count == 1
    assert err_msg == 'Cannot change the Slack channel name.'


def test_mirror_investigation_existing_investigation(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}

    mocker.patch.object(demisto, 'args', return_value={'type': 'chat', 'autoclose': 'false',
                                                       'direction': 'FromDemisto', 'mirrorTo': 'group'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681', 'users': ['spengler']})
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'GKQ86DVPH',
        'investigation_id': '681',
        'channel_name': 'incident-681',
        'channel_topic': 'incident-681',
        'mirror_type': 'chat',
        'mirror_direction': 'FromDemisto',
        'mirror_to': 'group',
        'auto_close': False,
        'mirrored': False
    }
    # Arrange

    mirror_investigation()

    calls = slack_sdk.WebClient.api_call.call_args_list
    channels_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']

    # Assert
    assert len(channels_call) == 0
    assert len(users_call) == 0
    assert len(invite_call) == 0
    assert len(topic_call) == 0

    success_results = demisto.results.call_args_list[0][0]
    assert success_results[0] == 'Investigation mirrored successfully, channel: incident-681'

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    our_mirror_filter = list(filter(lambda m: '681' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    assert len(our_mirror_filter) == 1
    assert our_mirror == new_mirror


def test_mirror_investigation_existing_channel(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}

    mocker.patch.object(demisto, 'args', return_value={'channelName': 'group3', 'type': 'chat', 'autoclose': 'false',
                                                       'direction': 'FromDemisto', 'mirrorTo': 'group'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '999', 'users': ['spengler']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'GKNEJU4P9',
        'channel_name': 'group3',
        'investigation_id': '999',
        'channel_topic': 'incident-713, incident-999',
        'mirror_type': 'chat',
        'mirror_direction': 'FromDemisto',
        'mirror_to': 'group',
        'auto_close': False,
        'mirrored': False
    }
    # Arrange

    mirror_investigation()

    calls = slack_sdk.WebClient.api_call.call_args_list
    groups_call = [c for c in calls if c[0][0] == 'groups.create']
    channels_call = [c for c in calls if c[0][0] == 'channels.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']

    # Assert

    assert len(groups_call) == 0
    assert len(channels_call) == 0
    assert len(users_call) == 0
    assert len(invite_call) == 0
    assert len(topic_call) == 1

    success_results = demisto.results.call_args_list[0][0]
    assert success_results[0] == 'Investigation mirrored successfully, channel: group3'

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    assert len(our_mirror_filter) == 1
    assert our_mirror == new_mirror


def test_mirror_investigation_existing_channel_remove_mirror(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}

    mirrors = js.loads(MIRRORS)
    mirrors.append({
        'channel_id': 'GKB19PA3V',
        'channel_name': 'group2',
        'channel_topic': 'cooltopic',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': True
    })

    set_integration_context({
        'mirrors': js.dumps(mirrors),
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    mocker.patch.object(demisto, 'investigation', return_value={'id': '999', 'users': ['spengler']})
    mocker.patch.object(demisto, 'args', return_value={'type': 'none'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'GKB19PA3V',
        'channel_name': 'group2',
        'channel_topic': 'cooltopic',
        'investigation_id': '999',
        'mirror_type': 'none',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    }
    # Arrange

    mirror_investigation()

    calls = slack_sdk.WebClient.api_call.call_args_list
    channels_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']

    # Assert
    assert len(channels_call) == 0
    assert len(users_call) == 0
    assert len(invite_call) == 0
    assert len(topic_call) == 0

    success_results = demisto.results.call_args_list[0][0]
    assert success_results[0] == 'Investigation mirrored successfully, channel: group2'

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    assert len(our_mirror_filter) == 1
    assert our_mirror == new_mirror


def test_mirror_investigation_existing_channel_with_topic(mocker):
    from SlackV3 import mirror_investigation

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}

    mocker.patch.object(demisto, 'args', return_value={'channelName': 'group2', 'type': 'chat', 'autoclose': 'false',
                                                       'direction': 'FromDemisto', 'mirrorTo': 'group'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '999', 'users': ['spengler']})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    new_mirror = {
        'channel_id': 'GKB19PA3V',
        'channel_name': 'group2',
        'channel_topic': 'cooltopic',
        'investigation_id': '999',
        'mirror_type': 'chat',
        'mirror_direction': 'FromDemisto',
        'mirror_to': 'group',
        'auto_close': False,
        'mirrored': False,
    }
    # Arrange

    mirror_investigation()

    calls = slack_sdk.WebClient.api_call.call_args_list
    channels_call = [c for c in calls if c[0][0] == 'conversations.create']
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']
    topic_call = [c for c in calls if c[0][0] == 'conversations.setTopic']

    # Assert
    assert len(channels_call) == 0
    assert len(users_call) == 0
    assert len(invite_call) == 0
    assert len(topic_call) == 0

    success_results = demisto.results.call_args_list[0][0]
    assert success_results[0] == 'Investigation mirrored successfully, channel: group2'

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    assert len(our_mirror_filter) == 1
    assert our_mirror == new_mirror


def test_check_for_mirrors(mocker):
    from SlackV3 import check_for_mirrors

    new_user = {
        'name': 'perikles',
        'profile': {
            'email': 'perikles@acropoli.com',
            'display_name': 'Dingus',
            'real_name': 'Lingus'
        },
        'id': 'U012B3CUI'
    }

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            users = {'members': js.loads(USERS)}
            users['members'].append(new_user)
            return users
        elif method == 'users.lookupByEmail':
            return {'user': new_user}

    # Set
    mirrors = js.loads(MIRRORS)
    mirrors.append({
        'channel_id': 'new_group',
        'channel_name': 'channel',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    })

    set_integration_context({
        'mirrors': js.dumps(mirrors),
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    new_mirror = {
        'channel_id': 'new_group',
        'channel_name': 'channel',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': True
    }

    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'mirrorInvestigation', return_value=[{'email': 'spengler@ghostbusters.example.com',
                                                                       'username': 'spengler'},
                                                                      {'email': 'perikles@acropoli.com',
                                                                       'username': 'perikles'}])

    # Arrange
    check_for_mirrors()

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.lookupByEmail']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']

    mirror_id = demisto.mirrorInvestigation.call_args[0][0]
    mirror_type = demisto.mirrorInvestigation.call_args[0][1]
    auto_close = demisto.mirrorInvestigation.call_args[0][2]

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    new_users = js.loads(new_context['users'])
    our_mirror_filter = list(filter(lambda m: '999' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]
    our_user_filter = list(filter(lambda u: 'U012B3CUI' == u['id'], new_users))
    our_user = our_user_filter[0]

    invited_users = [c[1]['json']['users'] for c in invite_call]
    channel = [c[1]['json']['channel'] for c in invite_call]

    # Assert
    assert len(users_call) == 1
    assert len(invite_call) == 2
    assert invited_users == ['U012A3CDE', 'U012B3CUI']
    assert channel == ['new_group', 'new_group']
    assert demisto.setIntegrationContext.call_count == 1
    assert len(our_mirror_filter) == 1
    assert our_mirror == new_mirror
    assert len(our_user_filter) == 1
    assert our_user == new_user

    assert mirror_id == '999'
    assert mirror_type == 'all:both'
    assert auto_close is True


def test_check_for_mirrors_no_updates(mocker):
    from SlackV3 import check_for_mirrors

    # Set
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)

    # Arrange
    check_for_mirrors()

    # Assert
    assert demisto.getIntegrationContext.call_count == 1
    assert demisto.setIntegrationContext.call_count == 0


def test_check_for_mirrors_email_user_not_matching(mocker):
    from SlackV3 import check_for_mirrors

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        new_user = {
            'name': 'nope',
            'profile': {
                'email': 'perikles@acropoli.com',
            },
            'id': 'U012B3CUI'
        }
        if method == 'users.list':
            users = {'members': js.loads(USERS)}
            users['members'].append(new_user)
            return users
        elif method == 'users.lookupByEmail':
            return {'user': new_user}

    # Set
    mirrors = js.loads(MIRRORS)
    mirrors.append({
        'channel_id': 'new_group',
        'channel_name': 'channel',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    })

    set_integration_context({
        'mirrors': js.dumps(mirrors),
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'mirrorInvestigation', return_value=[{'email': 'spengler@ghostbusters.example.com',
                                                                       'username': 'spengler'},
                                                                      {'email': 'perikles@acropoli.com',
                                                                       'username': 'perikles'}])

    # Arrange
    check_for_mirrors()

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.lookupByEmail']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']

    invited_users = [c[1]['json']['users'] for c in invite_call]
    channel = [c[1]['json']['channel'] for c in invite_call]
    assert demisto.setIntegrationContext.call_count == 1

    # Assert
    assert len(users_call) == 1
    assert len(invite_call) == 2
    assert invited_users == ['U012A3CDE', 'U012B3CUI']
    assert channel == ['new_group', 'new_group']


def test_check_for_mirrors_email_not_matching(mocker):
    from SlackV3 import check_for_mirrors

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        users = {'members': js.loads(USERS)}
        new_user = {
            'name': 'perikles',
            'profile': {
                'email': 'bruce.wayne@pharmtech.zz',
            },
            'id': 'U012B3CUI'
        }

        users['members'].append(new_user)
        return users

    # Set
    mirrors = js.loads(MIRRORS)
    mirrors.append({
        'channel_id': 'new_group',
        'channel_name': 'channel',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    })

    set_integration_context({
        'mirrors': js.dumps(mirrors),
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'mirrorInvestigation', return_value=[{'email': 'spengler@ghostbusters.example.com',
                                                                       'username': 'spengler'},
                                                                      {'email': '',
                                                                       'username': 'perikles'}])

    # Arrange
    check_for_mirrors()

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.list']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']

    invited_users = [c[1]['json']['users'] for c in invite_call]
    channel = [c[1]['json']['channel'] for c in invite_call]

    # Assert
    assert len(users_call) == 1
    assert len(invite_call) == 2
    assert invited_users == ['U012A3CDE', 'U012B3CUI']
    assert channel == ['new_group', 'new_group']
    assert demisto.setIntegrationContext.call_count == 1


def test_check_for_mirrors_user_email_not_matching(mocker):
    from SlackV3 import check_for_mirrors

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        new_user = {
            'name': 'perikles',
            'profile': {
                'email': 'perikles@acropoli.com',
            },
            'id': 'U012B3CUI'
        }
        if method == 'users.list':
            users = {'members': js.loads(USERS)}
            users['members'].append(new_user)
            return users
        elif method == 'users.lookupByEmail':
            return {'user': {}}

    # Set
    mirrors = js.loads(MIRRORS)
    mirrors.append({
        'channel_id': 'new_group',
        'channel_name': 'channel',
        'investigation_id': '999',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': False
    })

    set_integration_context({
        'mirrors': js.dumps(mirrors),
        'users': USERS,
        'conversations': CONVERSATIONS,
        'bot_id': 'W12345678'
    })

    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'mirrorInvestigation', return_value=[{'email': 'spengler@ghostbusters.example.com',
                                                                       'username': 'spengler'},
                                                                      {'email': 'bruce.wayne@pharmtech.zz',
                                                                       'username': '123'}])
    mocker.patch.object(demisto, 'results')

    # Arrange
    check_for_mirrors()

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.lookupByEmail']
    invite_call = [c for c in calls if c[0][0] == 'conversations.invite']

    invited_users = [c[1]['json']['users'] for c in invite_call]
    channel = [c[1]['json']['channel'] for c in invite_call]

    error_results = demisto.results.call_args_list[0][0]

    # Assert
    assert demisto.setIntegrationContext.call_count == 1
    assert error_results[0]['Contents'] == 'User bruce.wayne@pharmtech.zz not found in Slack'
    assert len(users_call) == 1
    assert len(invite_call) == 1
    assert invited_users == ['U012A3CDE']
    assert channel == ['new_group']


@pytest.mark.asyncio
async def test_handle_dm_create_demisto_user(mocker):
    import SlackV3

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.open':
            return {
                'channel': {
                    'id': 'ey'
                }}
        else:
            return 'sup'

    async def fake_translate(message: str, user_name: str, user_email: str, demisto_user: dict):
        return "sup"

    socket_client = AsyncMock()

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'findUser', return_value={'id': 'demisto_id'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'translate_create', side_effect=fake_translate)
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)

    user = js.loads(USERS)[0]

    # Arrange
    await SlackV3.handle_dm(user, 'open 123 incident', socket_client)
    await SlackV3.handle_dm(user, 'new incident abu ahmad', socket_client)
    await SlackV3.handle_dm(user, 'incident create 817', socket_client)
    await SlackV3.handle_dm(user, 'incident open', socket_client)
    await SlackV3.handle_dm(user, 'incident new', socket_client)
    await SlackV3.handle_dm(user, 'create incident name=abc type=Access', socket_client)

    # Assert
    assert SlackV3.translate_create.call_count == 6

    incident_string = SlackV3.translate_create.call_args[0][0]
    user_name = SlackV3.translate_create.call_args[0][1]
    user_email = SlackV3.translate_create.call_args[0][2]
    demisto_user = SlackV3.translate_create.call_args[0][3]

    assert demisto_user == {'id': 'demisto_id'}
    assert user_name == 'spengler'
    assert user_email == 'spengler@ghostbusters.example.com'
    assert incident_string == 'create incident name=abc type=Access'


@pytest.mark.asyncio
async def test_handle_dm_nondemisto_user_shouldnt_create(mocker):
    import SlackV3

    # Set
    async def fake_translate(message: str, user_name: str, user_email: str, demisto_user: dict):
        return "sup"

    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.open':
            return {
                'channel': {
                    'id': 'ey'
                }}
        else:
            return 'sup'

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'findUser', return_value=None)
    mocker.patch.object(SlackV3, 'translate_create', side_effect=fake_translate)
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)
    user = js.loads(USERS)[0]

    # Arrange
    await SlackV3.handle_dm(user, 'create incident abc', socket_client)

    # Assert
    assert SlackV3.translate_create.call_count == 0


@pytest.mark.asyncio
async def test_handle_dm_nondemisto_user_should_create(mocker):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'allow_incidents': 'true'})

    SlackV3.init_globals()

    # Set
    async def fake_translate(message: str, user_name: str, user_email: str, demisto_user: dict):
        return "sup"

    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.open':
            return {
                'channel': {
                    'id': 'ey'
                }}
        else:
            return 'sup'

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'findUser', return_value=None)
    mocker.patch.object(SlackV3, 'translate_create', side_effect=fake_translate)
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)
    user = js.loads(USERS)[0]

    # Arrange
    await SlackV3.handle_dm(user, 'create incident abc', socket_client)

    # Assert
    assert SlackV3.translate_create.call_count == 1

    demisto_user = SlackV3.translate_create.call_args[0][3]
    assert demisto_user is None


@pytest.mark.asyncio
async def test_handle_dm_non_create_nonexisting_user(mocker):
    from SlackV3 import handle_dm

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.open':
            return {
                'channel': {
                    'id': 'ey'
                }}
        else:
            return 'sup'

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'findUser', return_value=None)
    mocker.patch.object(demisto, 'directMessage', return_value=None)
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)
    user = js.loads(USERS)[0]

    # Arrange
    await handle_dm(user, 'wazup', socket_client)

    message = demisto.directMessage.call_args[0][0]
    username = demisto.directMessage.call_args[0][1]
    email = demisto.directMessage.call_args[0][2]
    allow = demisto.directMessage.call_args[0][3]

    # Assert
    assert message == 'wazup'
    assert username == 'spengler'
    assert email == 'spengler@ghostbusters.example.com'
    assert allow is False


@pytest.mark.asyncio
async def test_handle_dm_empty_message(mocker):
    from SlackV3 import handle_dm

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.open':
            return {
                'channel': {
                    'id': 'ey'
                }}
        elif method == 'chat.postMessage':
            text = json['text']
            if not text:
                raise InterruptedError()
        else:
            return None

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'findUser', return_value=None)
    mocker.patch.object(demisto, 'directMessage', return_value=None)
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)
    user = js.loads(USERS)[0]

    # Arrange
    await handle_dm(user, 'wazup', socket_client)

    calls = socket_client.api_call.call_args_list
    chat_call = [c for c in calls if c[0][0] == 'chat.postMessage']
    message_args = chat_call[0][1]['json']

    # Assert
    assert message_args['text'] == 'Sorry, I could not perform the selected operation.'


@pytest.mark.asyncio
async def test_handle_dm_create_with_error(mocker):
    import SlackV3

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.open':
            return {
                'channel': {
                    'id': 'ey'
                }}
        else:
            return 'sup'

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'findUser', return_value={'id': 'demisto_id'})
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'translate_create', side_effect=InterruptedError('omg'))

    user = js.loads(USERS)[0]

    # Arrange
    await SlackV3.handle_dm(user, 'open 123 incident', socket_client)

    # Assert
    assert SlackV3.translate_create.call_count == 1

    demisto_user = SlackV3.translate_create.call_args[0][3]
    incident_string = SlackV3.translate_create.call_args[0][0]
    calls = socket_client.api_call.call_args_list
    chat_call = [c for c in calls if c[0][0] == 'chat.postMessage']
    message_args = chat_call[0][1]['json']

    assert demisto_user == {'id': 'demisto_id'}
    assert incident_string == 'open 123 incident'
    assert message_args == {'channel': 'ey', 'text': 'Failed creating incidents: omg'}


@pytest.mark.asyncio
async def test_translate_create(mocker):
    import SlackV3

    # Set
    async def this_doesnt_create_incidents(incidents_json, user_name, email, demisto_id):
        return {
            'id': 'new_incident',
            'name': 'New Incident'
        }

    mocker.patch.object(SlackV3, 'create_incidents', side_effect=this_doesnt_create_incidents)
    mocker.patch.object(demisto, 'demistoUrls', return_value={'server': 'https://www.eizelulz.com:8443'})

    demisto_user = {'id': 'demisto_user'}

    json_message = 'create incident json={“name”: “xyz”, “role”: “Analyst”}'
    wrong_json_message = 'create incident json={"name": "xyz"} name=abc'
    name_message = 'create incident name=eyy'
    name_type_message = 'create incident name= eyy type= Access'
    type_name_message = 'create incident  type= Access name= eyy'
    type_message = 'create incident type= Phishing'

    success_message = 'Successfully created incident New Incident.\n' \
                      ' View it on: https://www.eizelulz.com:8443#/WarRoom/new_incident'

    # Arrange
    json_data = await SlackV3.translate_create(json_message, 'spengler',
                                               'spengler@ghostbusters.example.com', demisto_user)
    wrong_json_data = await SlackV3.translate_create(wrong_json_message, 'spengler',
                                                     'spengler@ghostbusters.example.com', demisto_user)
    name_data = await SlackV3.translate_create(name_message, 'spengler',
                                               'spengler@ghostbusters.example.com', demisto_user)
    name_type_data = await SlackV3.translate_create(name_type_message, 'spengler',
                                                    'spengler@ghostbusters.example.com', demisto_user)
    type_name_data = await SlackV3.translate_create(type_name_message, 'spengler',
                                                    'spengler@ghostbusters.example.com', demisto_user)
    type_data = await SlackV3.translate_create(type_message, 'spengler',
                                               'spengler@ghostbusters.example.com', demisto_user)

    create_args = SlackV3.create_incidents.call_args_list
    json_args = create_args[0][0][0]
    name_args = create_args[1][0][0]
    name_type_args = create_args[2][0][0]
    type_name_args = create_args[3][0][0]

    # Assert

    assert SlackV3.create_incidents.call_count == 4

    assert json_args == [{"name": "xyz", "role": "Analyst"}]
    assert name_args == [{"name": "eyy"}]
    assert name_type_args == [{"name": "eyy", "type": "Access"}]
    assert type_name_args == [{"name": "eyy", "type": "Access"}]

    assert json_data == success_message
    assert wrong_json_data == 'No other properties other than json should be specified.'
    assert name_data == success_message
    assert name_type_data == success_message
    assert type_name_data == success_message
    assert type_data == 'Please specify arguments in the following manner: name=<name> type=[type] or json=<json>.'


@pytest.mark.asyncio
async def test_translate_create_newline_json(mocker):
    # Set
    import SlackV3

    async def this_doesnt_create_incidents(incidents_json, user_name, email, demisto_id):
        return {
            'id': 'new_incident',
            'name': 'New Incident'
        }

    mocker.patch.object(SlackV3, 'create_incidents', side_effect=this_doesnt_create_incidents)
    mocker.patch.object(demisto, 'demistoUrls', return_value={'server': 'https://www.eizelulz.com:8443'})

    demisto_user = {'id': 'demisto_user'}

    json_message = \
        '''```
            create incident json={
            "name":"xyz",
            "details": "1.1.1.1,8.8.8.8"
            ```
        }'''

    success_message = 'Successfully created incident New Incident.\n' \
                      ' View it on: https://www.eizelulz.com:8443#/WarRoom/new_incident'

    # Arrange
    json_data = await SlackV3.translate_create(json_message, 'spengler', 'spengler@ghostbusters.example.com',
                                               demisto_user)

    create_args = SlackV3.create_incidents.call_args
    json_args = create_args[0][0]

    # Assert

    assert SlackV3.create_incidents.call_count == 1

    assert json_args == [{"name": "xyz", "details": "1.1.1.1,8.8.8.8"}]

    assert json_data == success_message


@pytest.mark.asyncio
async def test_create_incidents_no_labels(mocker):
    from SlackV3 import create_incidents

    # Set
    mocker.patch.object(demisto, 'createIncidents', return_value='nice')

    incidents = [{"name": "xyz", "details": "1.1.1.1,8.8.8.8"}]

    incidents_with_labels = [{'name': 'xyz', 'details': '1.1.1.1,8.8.8.8',
                              'labels': [{'type': 'Reporter', 'value': 'spengler'},
                                         {'type': 'ReporterEmail', 'value': 'spengler@ghostbusters.example.com'},
                                         {'type': 'Source', 'value': 'Slack'}]}]

    # Arrange
    data = await create_incidents(incidents, 'spengler', 'spengler@ghostbusters.example.com', 'demisto_user')

    incident_arg = demisto.createIncidents.call_args[0][0]
    user_arg = demisto.createIncidents.call_args[1]['userID']

    assert incident_arg == incidents_with_labels
    assert user_arg == 'demisto_user'
    assert data == 'nice'


@pytest.mark.asyncio
async def test_create_incidents_with_labels(mocker):
    from SlackV3 import create_incidents

    # Set
    mocker.patch.object(demisto, 'createIncidents', return_value='nice')

    incidents = [{'name': 'xyz', 'details': '1.1.1.1,8.8.8.8',
                  'labels': [{'type': 'Reporter', 'value': 'spengler'},
                             {'type': 'ReporterEmail', 'value': 'spengler@ghostbusters.example.com'}]}]

    incidents_with_labels = [{'name': 'xyz', 'details': '1.1.1.1,8.8.8.8',
                              'labels': [{'type': 'Reporter', 'value': 'spengler'},
                                         {'type': 'ReporterEmail', 'value': 'spengler@ghostbusters.example.com'},
                                         {'type': 'Source', 'value': 'Slack'}]}]

    # Arrange
    data = await create_incidents(incidents, 'spengler', 'spengler@ghostbusters.example.com', 'demisto_user')

    incident_arg = demisto.createIncidents.call_args[0][0]
    user_arg = demisto.createIncidents.call_args[1]['userID']

    assert incident_arg == incidents_with_labels
    assert user_arg == 'demisto_user'
    assert data == 'nice'


@pytest.mark.asyncio
async def test_get_user_by_id_async_user_exists(mocker):
    from SlackV3 import get_user_by_id_async

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.info':
            return {'user': js.loads(USERS)[0]}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    user_id = 'U012A3CDE'

    # Arrange
    user = await get_user_by_id_async(slack_sdk.WebClient, user_id)

    # Assert
    assert slack_sdk.WebClient.api_call.call_count == 0
    assert demisto.setIntegrationContext.call_count == 0
    assert user['name'] == 'spengler'


@pytest.mark.asyncio
async def test_get_user_by_id_async_user_doesnt_exist(mocker):
    from SlackV3 import get_user_by_id_async

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.info':
            return {'user': js.loads(USERS)[0]}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext')
    socket_client = AsyncMock()
    mocker.patch.object(socket_client, 'api_call', side_effect=api_call)

    user_id = 'XXXXXXX'

    # Arrange
    user = await get_user_by_id_async(socket_client, user_id)

    # Assert

    assert socket_client.api_call.call_count == 1
    assert demisto.setIntegrationContext.call_count == 1
    assert user['name'] == 'spengler'


@pytest.mark.asyncio
async def test_handle_text(mocker):
    import SlackV3

    # Set
    async def fake_clean(text, client):
        return 'מה הולך'

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'addEntry')
    mocker.patch.object(SlackV3, 'clean_message', side_effect=fake_clean)

    user = js.loads(USERS)[0]
    investigation_id = '999'
    text = 'מה הולך'

    # Arrange
    await SlackV3.handle_text(slack_sdk.WebClient, investigation_id, text, user)
    entry_args = demisto.addEntry.call_args[1]

    # Assert
    assert demisto.addEntry.call_count == 1
    assert entry_args['id'] == '999'
    assert entry_args['entry'] == 'מה הולך'
    assert entry_args['username'] == 'spengler'
    assert entry_args['email'] == 'spengler@ghostbusters.example.com'
    assert entry_args['footer'] == '\n**From Slack**'


@pytest.mark.asyncio
async def test_check_entitlement(mocker):
    from SlackV3 import check_and_handle_entitlement

    # Set
    mocker.patch.object(demisto, 'handleEntitlementForUser')

    user = {
        'id': 'U123456',
        'name': 'test',
        'profile': {
            'email': 'test@demisto.com'
        }
    }

    message1 = 'hi test@demisto.com 4404dae8-2d45-46bd-85fa-64779c12abe8@e093ba05-3f3c-402e-81a7-149db969be5d goodbye'
    message2 = 'hi test@demisto.com 4404dae8-2d45-46bd-85fa-64779c12abe8@22 goodbye'
    message3 = 'hi test@demisto.com 4404dae8-2d45-46bd-85fa-64779c12abe8@e093ba05-3f3c-402e-81a7-149db969be5d|4 goodbye'
    message4 = 'hi test@demisto.com 4404dae8-2d45-46bd-85fa-64779c12abe8@22|43 goodbye'
    message5 = 'hi test@demisto.com 43434@e093ba05-3f3c-402e-81a7-149db969be5d goodbye'
    message6 = 'hi test@demisto.com name-of-someone@mail-of-someone goodbye'
    message7 = 'hi test@demisto.com 4404dae8-2d45-46bd-85fa-64779c12abe8@22_1|43 goodbye'
    message8 = 'hi test@demisto.com 4404dae8-2d45-46bd-85fa-64779c12abe8@22_2 goodbye'

    # Arrange
    result1 = await check_and_handle_entitlement(message1, user, '')
    result2 = await check_and_handle_entitlement(message2, user, '')
    result3 = await check_and_handle_entitlement(message3, user, '')
    result4 = await check_and_handle_entitlement(message4, user, '')
    result5 = await check_and_handle_entitlement(message5, user, '')
    result6 = await check_and_handle_entitlement(message6, user, '')
    result7 = await check_and_handle_entitlement(message7, user, '')
    result8 = await check_and_handle_entitlement(message8, user, '')

    result1_args = demisto.handleEntitlementForUser.call_args_list[0][0]
    result2_args = demisto.handleEntitlementForUser.call_args_list[1][0]
    result3_args = demisto.handleEntitlementForUser.call_args_list[2][0]
    result4_args = demisto.handleEntitlementForUser.call_args_list[3][0]
    result7_args = demisto.handleEntitlementForUser.call_args_list[4][0]
    result8_args = demisto.handleEntitlementForUser.call_args_list[5][0]

    assert result1 == 'Thank you for your response.'
    assert result2 == 'Thank you for your response.'
    assert result3 == 'Thank you for your response.'
    assert result4 == 'Thank you for your response.'
    assert result5 == ''
    assert result6 == ''
    assert result7 == 'Thank you for your response.'
    assert result8 == 'Thank you for your response.'

    assert demisto.handleEntitlementForUser.call_count == 6

    assert result1_args[0] == 'e093ba05-3f3c-402e-81a7-149db969be5d'  # incident ID
    assert result1_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'  # GUID
    assert result1_args[2] == 'test@demisto.com'  # email
    assert result1_args[3] == 'hi test@demisto.com  goodbye'  # content
    assert result1_args[4] == ''  # task id

    assert result2_args[0] == '22'
    assert result2_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'
    assert result2_args[2] == 'test@demisto.com'
    assert result2_args[3] == 'hi test@demisto.com  goodbye'
    assert result2_args[4] == ''

    assert result3_args[0] == 'e093ba05-3f3c-402e-81a7-149db969be5d'
    assert result3_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'
    assert result3_args[2] == 'test@demisto.com'
    assert result3_args[3] == 'hi test@demisto.com  goodbye'
    assert result3_args[4] == '4'

    assert result4_args[0] == '22'
    assert result4_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'
    assert result4_args[2] == 'test@demisto.com'
    assert result4_args[3] == 'hi test@demisto.com  goodbye'
    assert result4_args[4] == '43'

    assert result7_args[0] == '22_1'
    assert result7_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'
    assert result7_args[2] == 'test@demisto.com'
    assert result7_args[3] == 'hi test@demisto.com  goodbye'
    assert result7_args[4] == '43'

    assert result8_args[0] == '22_2'
    assert result8_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'
    assert result8_args[2] == 'test@demisto.com'
    assert result8_args[3] == 'hi test@demisto.com  goodbye'
    assert result8_args[4] == ''


@pytest.mark.asyncio
async def test_check_entitlement_with_context(mocker):
    from SlackV3 import check_and_handle_entitlement

    # Set
    mocker.patch.object(demisto, 'handleEntitlementForUser')
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)

    user = {
        'id': 'U123456',
        'name': 'test',
        'profile': {
            'email': 'test@demisto.com'
        }
    }

    integration_context = get_integration_context()
    integration_context['questions'] = js.dumps([{
        'thread': 'cool',
        'entitlement': '4404dae8-2d45-46bd-85fa-64779c12abe8@22|43'
    }, {
        'thread': 'notcool',
        'entitlement': '4404dae8-2d45-46bd-85fa-64779c12abe8@30|44'
    }])

    set_integration_context(integration_context)

    # Arrange
    await check_and_handle_entitlement('hola', user, 'cool')

    result_args = demisto.handleEntitlementForUser.call_args_list[0][0]

    # Assert
    assert demisto.handleEntitlementForUser.call_count == 1

    assert result_args[0] == '22'
    assert result_args[1] == '4404dae8-2d45-46bd-85fa-64779c12abe8'
    assert result_args[2] == 'test@demisto.com'
    assert result_args[3] == 'hola'
    assert result_args[4] == '43'

    # Should delete the question
    assert demisto.getIntegrationContext()['questions'] == js.dumps([{
        'thread': 'notcool',
        'entitlement': '4404dae8-2d45-46bd-85fa-64779c12abe8@30|44'
    }])


def test_send_request(mocker):
    import SlackV3

    # Set
    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_file', return_value='neat')
    mocker.patch.object(SlackV3, 'send_message', return_value='cool')

    # Arrange

    user_res = SlackV3.slack_send_request('spengler', None, None, message='Hi')
    channel_res = SlackV3.slack_send_request(None, 'general', None, file_dict='file')

    user_args = SlackV3.send_message.call_args[0]
    channel_args = SlackV3.send_file.call_args[0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1
    assert SlackV3.send_file.call_count == 1

    assert user_args[0] == ['im_channel']
    assert user_args[1] == ''
    assert user_args[2] is False
    assert user_args[4] == 'Hi'
    assert user_args[5] == ''

    assert channel_args[0] == ['C012AB3CD']
    assert channel_args[1] == 'file'
    assert channel_args[3] == ''

    assert user_res == 'cool'
    assert channel_res == 'neat'


def test_send_request_channel_id(mocker):
    """
    Given:
        Test Case 1: A valid Channel ID as a destination to send a message to.
        Test Case 2: A valid Channel ID as a destination to send a file to.
    When:
        Test Case 1: Sending a message using a channel_id
        Test Case 2: Sending a file using a channel_id
    Then:
        Test Case 1: Assert that the endpoint was called using only the channel_id, and no other calls were made.
        Test Case 2: Assert that the endpoint was called using only the channel_id, and no other calls were made.
    """
    import SlackV3

    # Set
    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_file', return_value='neat')
    mocker.patch.object(SlackV3, 'send_message', return_value='cool')

    # Arrange

    channel_id_text_res = SlackV3.slack_send_request(to=None, channel=None, group=None, message='Hi', channel_id='C12345')
    channel_id_file_res = SlackV3.slack_send_request(to=None, channel=None, group=None, channel_id='C12345',
                                                     file_dict={'foo': 'file'})

    channel_id_text_args = SlackV3.send_message.call_args[0]
    channel_id_file_args = SlackV3.send_file.call_args[0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert
    # Assert that NO user or channel APIs were called.
    assert len(users_call) == 0
    assert len(conversations_call) == 0

    assert SlackV3.send_message.call_count == 1
    assert SlackV3.send_file.call_count == 1

    assert channel_id_text_args[0] == ['C12345']
    assert channel_id_text_args[1] == ''
    assert channel_id_text_args[2] is False
    assert channel_id_text_args[4] == 'Hi'
    assert channel_id_text_args[5] == ''

    assert channel_id_file_args[0] == ['C12345']
    assert channel_id_file_args[1] == {'foo': 'file'}
    assert channel_id_file_args[3] == ''

    assert channel_id_text_res == 'cool'
    assert channel_id_file_res == 'neat'


def test_send_request_caching_disabled(mocker, capfd):
    import SlackV3

    # Set
    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_file', return_value='neat')
    mocker.patch.object(SlackV3, 'send_message', return_value='cool')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    SlackV3.DISABLE_CACHING = True
    # Arrange

    channel_id_text_res = SlackV3.slack_send_request(to=None, channel=None, group=None, message='Hi',
                                                     channel_id='C12345')
    channel_id_file_res = SlackV3.slack_send_request(to=None, channel=None, group=None, channel_id='C12345',
                                                     file_dict={'foo': 'file'})
    with capfd.disabled():
        with pytest.raises(InterruptedError):
            SlackV3.slack_send_request(to=None, channel='should-fail', group=None, message='Hi',
                                       channel_id=None)
    err_msg_1 = return_error_mock.call_args[0][0]

    assert err_msg_1 == "Could not find the Slack conversation should-fail. If caching is disabled, try searching by" \
                        " channel_id"

    with capfd.disabled():
        with pytest.raises(InterruptedError):
            SlackV3.slack_send_request(to=None, channel='should-fail', group=None, channel_id=None,
                                       file_dict={'foo': 'file'})
    err_msg_2 = return_error_mock.call_args[0][0]

    assert err_msg_2 == "Could not find the Slack conversation should-fail. If caching is disabled, try searching by" \
                        " channel_id"

    channel_id_text_args = SlackV3.send_message.call_args[0]
    channel_id_file_args = SlackV3.send_file.call_args[0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert
    # Assert that NO user or channel APIs were called.
    assert len(users_call) == 0
    assert len(conversations_call) == 0

    assert SlackV3.send_message.call_count == 1
    assert SlackV3.send_file.call_count == 1

    assert channel_id_text_args[0] == ['C12345']
    assert channel_id_text_args[1] == ''
    assert channel_id_text_args[2] is False
    assert channel_id_text_args[4] == 'Hi'
    assert channel_id_text_args[5] == ''

    assert channel_id_file_args[0] == ['C12345']
    assert channel_id_file_args[1] == {'foo': 'file'}
    assert channel_id_file_args[3] == ''

    assert channel_id_text_res == 'cool'
    assert channel_id_file_res == 'neat'


def test_send_request_different_name(mocker):
    import SlackV3

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value='cool')

    # Arrange
    channel_res = SlackV3.slack_send_request(None, 'incident-684', None, message='Hi')

    channel_args = SlackV3.send_message.call_args[0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert channel_args[0] == ['GKB19PA3V']
    assert channel_args[1] == ''
    assert channel_args[2] is False
    assert channel_args[4] == 'Hi'
    assert channel_args[5] == ''

    assert channel_res == 'cool'


def test_send_request_with_severity(mocker):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'incidentNotificationChannel': 'general',
                                                         'min_severity': 'High',
                                                         'permitted_notifications': ['incidentOpened']})

    SlackV3.init_globals()

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={'severity': '3', 'message': '!!!',
                                                       'messageType': 'incidentOpened'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange
    SlackV3.DISABLE_CACHING = False
    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']
    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['C012AB3CD']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == '!!!'
    assert send_args[5] == ''

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'


def test_send_request_with_notification_channel(mocker):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'incidentNotificationChannel': 'general',
                                                         'min_severity': 'High', 'notify_incidents': True,
                                                         'permitted_notifications': ['incidentOpened']})

    SlackV3.init_globals()

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={'channel': 'incidentNotificationChannel',
                                                       'severity': '4', 'message': '!!!',
                                                       'messageType': 'incidentOpened'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange
    SlackV3.DISABLE_CACHING = False
    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['C012AB3CD']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == '!!!'
    assert send_args[5] == ''

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'


@pytest.mark.parametrize('notify', [False, True])
def test_send_request_with_notification_channel_as_dest(mocker, notify):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'incidentNotificationChannel': 'general',
                                                         'min_severity': 'High', 'notify_incidents': notify})

    SlackV3.init_globals()

    # Set
    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={'channel': 'general', 'message': '!!!'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange
    SlackV3.DISABLE_CACHING = False
    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['C012AB3CD']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == '!!!'
    assert send_args[5] == ''

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'


def test_send_request_with_entitlement(mocker):
    import SlackV3

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={
        'message': js.dumps({
            'message': 'hi test@demisto.com',
            'entitlement': '4404dae8-2d45-46bd-85fa-64779c12abe8@22|43',
            'reply': 'Thanks bro',
            'expiry': '2019-09-26 18:38:25',
            'default_response': 'NoResponse'}),
        'to': 'spengler'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)
    mocker.patch.object(SlackV3, 'get_current_utc_time', return_value=datetime.datetime(2019, 9, 26, 18, 38, 25))
    questions = [{
        'thread': 'cool',
        'entitlement': '4404dae8-2d45-46bd-85fa-64779c12abe8@22|43',
        'reply': 'Thanks bro',
        'expiry': '2019-09-26 18:38:25',
        'sent': '2019-09-26 18:38:25',
        'default_response': 'NoResponse'
    }]

    # Arrange
    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['im_channel']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == 'hi test@demisto.com'
    assert send_args[5] == ''

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'

    assert demisto.getIntegrationContext()['questions'] == js.dumps(questions)


def test_send_request_with_entitlement_blocks(mocker):
    import SlackV3

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={
        'blocks': js.dumps({
            'blocks': js.dumps(BLOCK_JSON),
            'entitlement': 'e95cb5a1-e394-4bc5-8ce0-508973aaf298@22|43',
            'reply': 'Thanks bro',
            'expiry': '2019-09-26 18:38:25',
            'default_response': 'NoResponse'}),
        'to': 'spengler'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)
    mocker.patch.object(SlackV3, 'get_current_utc_time', return_value=datetime.datetime(2019, 9, 26, 18, 38, 25))
    questions = [{
        'thread': 'cool',
        'entitlement': 'e95cb5a1-e394-4bc5-8ce0-508973aaf298@22|43',
        'reply': 'Thanks bro',
        'expiry': '2019-09-26 18:38:25',
        'sent': '2019-09-26 18:38:25',
        'default_response': 'NoResponse'
    }]

    # Arrange
    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['im_channel']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == ''
    assert send_args[6] == js.dumps(BLOCK_JSON)

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'

    assert demisto.getIntegrationContext()['questions'] == js.dumps(questions)


def test_send_request_with_entitlement_blocks_message(mocker):
    import SlackV3

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={
        'message': 'wat up',
        'blocks': js.dumps({
            'blocks': js.dumps(BLOCK_JSON),
            'entitlement': 'e95cb5a1-e394-4bc5-8ce0-508973aaf298@22|43',
            'reply': 'Thanks bro',
            'expiry': '2019-09-26 18:38:25',
            'default_response': 'NoResponse'}),
        'to': 'spengler'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)
    mocker.patch.object(SlackV3, 'get_current_utc_time', return_value=datetime.datetime(2019, 9, 26, 18, 38, 25))

    questions = [{
        'thread': 'cool',
        'entitlement': 'e95cb5a1-e394-4bc5-8ce0-508973aaf298@22|43',
        'reply': 'Thanks bro',
        'expiry': '2019-09-26 18:38:25',
        'sent': '2019-09-26 18:38:25',
        'default_response': 'NoResponse'
    }]

    # Arrange
    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['im_channel']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == 'wat up'
    assert send_args[6] == js.dumps(BLOCK_JSON)

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'

    assert demisto.getIntegrationContext()['questions'] == js.dumps(questions)


def test_send_to_user_lowercase(mocker):
    import SlackV3

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'args', return_value={'to': 'glenda@south.oz.coven', 'message': 'hi'})
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_file', return_value='neat')
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange

    SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 0
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['im_channel']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == 'hi'
    assert send_args[5] == ''

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'


def test_send_request_with_severity_user_doesnt_exist(mocker, capfd):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'incidentNotificationChannel': 'general',
                                                         'min_severity': 'High', 'notify_incidents': True,
                                                         'permitted_notifications': ['incidentOpened']})

    SlackV3.init_globals()
    SlackV3.DISABLE_CACHING = False
    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={'severity': '3', 'message': '!!!',
                                                       'messageType': 'incidentOpened', 'to': 'alexios'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext')
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange
    with capfd.disabled():
        SlackV3.slack_send()

    send_args = SlackV3.send_message.call_args[0]

    results = demisto.results.call_args_list[0][0]
    calls = slack_sdk.WebClient.api_call.call_args_list

    users_call = [c for c in calls if c[0][0] == 'users.list']
    conversations_call = [c for c in calls if c[0][0] == 'conversations.list']

    # Assert

    assert len(users_call) == 1
    assert len(conversations_call) == 0
    assert SlackV3.send_message.call_count == 1

    assert send_args[0] == ['C012AB3CD']
    assert send_args[1] is None
    assert send_args[2] is False
    assert send_args[4] == '!!!'
    assert send_args[5] == ''

    assert results[0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: cool'


def test_send_request_no_user(mocker, capfd):
    import SlackV3

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_file', return_value='neat')
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange

    with capfd.disabled():
        with pytest.raises(InterruptedError):
            SlackV3.slack_send_request('alexios', None, None, message='Hi')
    err_msg = return_error_mock.call_args[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.list']

    # Assert

    assert return_error_mock.call_count == 1
    assert err_msg == 'Could not find any destination to send to.'
    assert len(users_call) == 1
    assert SlackV3.send_message.call_count == 0
    assert SlackV3.send_file.call_count == 0


def test_send_request_no_severity(mocker):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'incidentNotificationChannel': 'general',
                                                         'min_severity': 'High', 'notify_incidents': True,
                                                         'permitted_notifications': ['incidentOpened']})

    SlackV3.init_globals()

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={'severity': '2', 'message': '!!!',
                                                       'messageType': 'incidentOpened'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.slack_send()

    err_msg = return_error_mock.call_args[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.list']

    # Assert

    assert return_error_mock.call_count == 1
    assert err_msg == 'Either a user, group, channel id, or channel must be provided.'
    assert len(users_call) == 0
    assert SlackV3.send_message.call_count == 0


def test_send_request_zero_severity(mocker):
    import SlackV3

    mocker.patch.object(demisto, 'params', return_value={'incidentNotificationChannel': 'general',
                                                         'min_severity': 'High', 'notify_incidents': True,
                                                         'permitted_notifications': ['incidentOpened']})

    SlackV3.init_globals()

    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        elif method == 'conversations.list':
            return {'channels': js.loads(CONVERSATIONS)}
        elif method == 'conversations.open':
            return {'channel': {'id': 'im_channel'}}
        return {}

    mocker.patch.object(demisto, 'args', return_value={'severity': '0', 'message': '!!!',
                                                       'messageType': 'incidentOpened'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    mocker.patch.object(SlackV3, 'send_message', return_value=SLACK_RESPONSE)

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.slack_send()

    err_msg = return_error_mock.call_args[0][0]

    calls = slack_sdk.WebClient.api_call.call_args_list
    users_call = [c for c in calls if c[0][0] == 'users.list']

    # Assert

    assert return_error_mock.call_count == 1
    assert err_msg == 'Either a user, group, channel id, or channel must be provided.'
    assert len(users_call) == 0
    assert SlackV3.send_message.call_count == 0


def test_send_message(mocker):
    import SlackV3
    # Set

    link = 'https://www.eizelulz.com:8443/#/WarRoom/727'
    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'demistoUrls', return_value={'warRoom': link})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'send_message_to_destinations')
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')

    # Arrange
    SlackV3.send_message(['channel'], None, None, demisto.getIntegrationContext(), 'yo', None, '')

    args = SlackV3.send_message_to_destinations.call_args[0]

    # Assert
    assert SlackV3.send_message_to_destinations.call_count == 1

    assert args[0] == ['channel']
    assert args[1] == 'yo' + '\nView it on: ' + link
    assert args[2] is None


def test_send_message_to_destinations(mocker):
    import SlackV3
    # Set

    link = 'https://www.eizelulz.com:8443/#/WarRoom/727'
    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'demistoUrls', return_value={'warRoom': link})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'send_slack_request_sync')

    # Arrange
    SlackV3.send_message_to_destinations(['channel'], 'yo', None, '')

    args = SlackV3.send_slack_request_sync.call_args[1]

    # Assert
    assert SlackV3.send_slack_request_sync.call_count == 1
    assert 'http_verb' not in args
    assert args['body']['channel'] == 'channel'
    assert args['body']['text']


def test_send_file_to_destinations(mocker):
    import SlackV3
    # Set

    link = 'https://www.eizelulz.com:8443/#/WarRoom/727'
    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'demistoUrls', return_value={'warRoom': link})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'send_slack_request_sync')

    # Arrange
    SlackV3.send_file_to_destinations(['channel'], {'name': 'name', 'path': 'yo'}, None)

    args = SlackV3.send_slack_request_sync.call_args[1]

    # Assert
    assert SlackV3.send_slack_request_sync.call_count == 1
    assert 'http_verb' not in args
    assert args['file_'] == 'yo'
    assert args['body']['filename'] == 'name'


def test_send_message_retry(mocker):
    import SlackV3
    from slack_sdk.errors import SlackApiError
    # Set

    link = 'https://www.eizelulz.com:8443/#/WarRoom/727'
    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'demistoUrls', return_value={'warRoom': link})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')

    # Arrange
    mocker.patch.object(SlackV3, 'send_message_to_destinations',
                        side_effect=[SlackApiError('not_in_channel', None), 'ok'])
    SlackV3.send_message(['channel'], None, None, demisto.getIntegrationContext(), 'yo', None, '')

    args = SlackV3.send_message_to_destinations.call_args_list[1][0]

    # Assert
    assert SlackV3.send_message_to_destinations.call_count == 2

    assert args[0] == ['channel']
    assert args[1] == 'yo' + '\nView it on: ' + link
    assert args[2] is None


def test_send_file_retry(mocker):
    import SlackV3
    from slack_sdk.errors import SlackApiError
    # Set

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')

    # Arrange
    mocker.patch.object(SlackV3, 'send_file_to_destinations',
                        side_effect=[SlackApiError('not_in_channel', None), 'ok'])
    SlackV3.send_file(['channel'], 'file', demisto.getIntegrationContext(), None)

    args = SlackV3.send_file_to_destinations.call_args_list[1][0]

    # Assert
    assert SlackV3.send_file_to_destinations.call_count == 2

    assert args[0] == ['channel']
    assert args[1] == 'file'
    assert args[2] is None


def test_close_channel_with_name(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'channel': 'general'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.close_channel()

    close_args = slack_sdk.WebClient.api_call.call_args
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 1
    assert slack_sdk.WebClient.api_call.call_count == 1
    assert success_results[0] == 'Channel successfully archived.'
    assert close_args[0][0] == 'conversations.archive'
    assert close_args[1]['json']['channel'] == 'C012AB3CD'


def test_close_channel_should_delete_mirror(mocker):
    from SlackV3 import close_channel
    # Set

    mirrors = js.loads(MIRRORS)
    mirrors.pop(0)

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'mirrorInvestigation')
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')

    # Arrange
    close_channel()

    archive_args = slack_sdk.WebClient.api_call.call_args
    context_args = demisto.setIntegrationContext.call_args[0][0]
    context_args_mirrors = js.loads(context_args['mirrors'])
    mirror_args = demisto.mirrorInvestigation.call_args[0]

    # Assert
    assert archive_args[0][0] == 'conversations.archive'
    assert archive_args[1]['json']['channel'] == 'GKQ86DVPH'
    assert context_args_mirrors == mirrors
    assert mirror_args == ('681', 'none:both', True)


def test_close_channel_should_delete_mirrors(mocker):
    from SlackV3 import close_channel
    # Set

    mirrors = js.loads(MIRRORS)
    mirrors.pop(1)
    mirrors.pop(1)

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'investigation', return_value={'id': '684'})
    mocker.patch.object(demisto, 'mirrorInvestigation')
    mocker.patch.object(slack_sdk.WebClient, 'api_call')

    # Arrange
    close_channel()

    archive_args = slack_sdk.WebClient.api_call.call_args
    context_args = demisto.setIntegrationContext.call_args[0][0]
    mirrors_args = [args[0] for args in demisto.mirrorInvestigation.call_args_list]
    context_args_mirrors = js.loads(context_args['mirrors'])

    # Assert
    assert archive_args[0][0] == 'conversations.archive'
    assert archive_args[1]['json']['channel'] == 'GKB19PA3V'
    assert context_args_mirrors == mirrors
    assert mirrors_args == [('684', 'none:both', True), ('692', 'none:both', True)]


def test_get_conversation_by_name_paging(mocker):
    from SlackV3 import get_conversation_by_name
    # Set

    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'conversations.list':
            if len(params) == 3:
                return {'channels': js.loads(CONVERSATIONS), 'response_metadata': {
                    'next_cursor': 'dGVhbTpDQ0M3UENUTks='
                }}
            else:
                return {'channels': [{
                    'id': 'C248918AB',
                    'name': 'lulz'
                }], 'response_metadata': {
                    'next_cursor': ''
                }}

    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    # Arrange
    channel = get_conversation_by_name('lulz')
    args = slack_sdk.WebClient.api_call.call_args_list
    first_args = args[0][1]
    second_args = args[1][1]

    # Assert
    assert args[0][0][0] == 'conversations.list'
    assert len(first_args['params']) == 3
    assert first_args['params']['limit'] == 200
    assert len(second_args['params']) == 4
    assert second_args['params']['cursor'] == 'dGVhbTpDQ0M3UENUTks='
    assert channel['id'] == 'C248918AB'
    assert slack_sdk.WebClient.api_call.call_count == 2


def test_send_file_no_args_investigation(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'getFilePath', return_value={'path': 'path', 'name': 'name'})
    mocker.patch.object(demisto, 'results')
    mocker.patch.object(SlackV3, 'slack_send_request', return_value='cool')

    # Arrange
    SlackV3.slack_send_file()

    send_args = SlackV3.slack_send_request.call_args
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.slack_send_request.call_count == 1
    assert success_results[0] == 'File sent to Slack successfully.'

    assert send_args[0][1] == 'incident-681'
    assert send_args[1]['file_dict'] == {
        'path': 'path',
        'name': 'name',
        'comment': ''
    }


def test_send_file_no_args_no_investigation(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '999'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'slack_send_request', return_value='cool')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.slack_send_file()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert SlackV3.slack_send_request.call_count == 0
    assert err_msg == 'Either a user, group, channel id or channel must be provided.'


def test_set_topic(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'channel': 'general', 'topic': 'ey'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.set_channel_topic()

    send_args = slack_sdk.WebClient.api_call.call_args
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 1
    assert slack_sdk.WebClient.api_call.call_count == 1
    assert success_results[0] == 'Topic successfully set.'
    assert send_args[0][0] == 'conversations.setTopic'
    assert send_args[1]['json']['channel'] == 'C012AB3CD'
    assert send_args[1]['json']['topic'] == 'ey'


def test_set_topic_no_args_investigation(mocker):
    import SlackV3

    # Set

    new_mirror = {
        'channel_id': 'GKQ86DVPH',
        'channel_name': 'incident-681',
        'channel_topic': 'ey',
        'investigation_id': '681',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': True
    }

    mocker.patch.object(demisto, 'args', return_value={'topic': 'ey'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.set_channel_topic()

    send_args = slack_sdk.WebClient.api_call.call_args
    success_results = demisto.results.call_args[0]

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    our_mirror_filter = list(filter(lambda m: '681' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert slack_sdk.WebClient.api_call.call_count == 1
    assert success_results[0] == 'Topic successfully set.'
    assert send_args[0][0] == 'conversations.setTopic'
    assert send_args[1]['json']['channel'] == 'GKQ86DVPH'
    assert send_args[1]['json']['topic'] == 'ey'
    assert new_mirror == our_mirror


def test_set_topic_no_args_no_investigation(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'topic': 'ey'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '9999'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.set_channel_topic()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert err_msg == 'The channel was not found. Either the Slack app is not a member of the channel, or the slack app ' \
                      'does not have permission to find the channel.'


def test_invite_users(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'channel': 'general', 'users': 'spengler, glinda'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.invite_to_channel()

    send_args = SlackV3.invite_users_to_conversation.call_args[0]
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 1
    assert SlackV3.invite_users_to_conversation.call_count == 1
    assert success_results[0] == 'Successfully invited users to the channel.'
    assert send_args[0] == 'C012AB3CD'
    assert send_args[1] == ['U012A3CDE', 'U07QCRPA4']


def test_invite_users_no_channel(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'users': 'spengler, glinda'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'GKQ86DVPH'})
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.invite_to_channel()

    send_args = SlackV3.invite_users_to_conversation.call_args[0]
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert SlackV3.invite_users_to_conversation.call_count == 1
    assert success_results[0] == 'Successfully invited users to the channel.'
    assert send_args[0] == 'GKQ86DVPH'
    assert send_args[1] == ['U012A3CDE', 'U07QCRPA4']


def test_invite_users_no_channel_doesnt_exist(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'users': 'spengler, glinda'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '777'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'GKQ86DVPH'})
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')
    mocker.patch.object(demisto, 'results')

    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.invite_to_channel()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert SlackV3.invite_users_to_conversation.call_count == 0
    assert err_msg == 'The channel was not found. Either the Slack app is not a member of the channel, or the slack app ' \
                      'does not have permission to find the channel.'


def test_kick_users(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'channel': 'general', 'users': 'spengler, glinda'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(SlackV3, 'kick_users_from_conversation')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.kick_from_channel()

    send_args = SlackV3.kick_users_from_conversation.call_args[0]
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 1
    assert SlackV3.kick_users_from_conversation.call_count == 1
    assert success_results[0] == 'Successfully kicked users from the channel.'
    assert send_args[0] == 'C012AB3CD'
    assert send_args[1] == ['U012A3CDE', 'U07QCRPA4']


def test_kick_users_no_channel(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'users': 'spengler, glinda'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'GKQ86DVPH'})
    mocker.patch.object(SlackV3, 'kick_users_from_conversation')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.DISABLE_CACHING = False
    SlackV3.kick_from_channel()

    send_args = SlackV3.kick_users_from_conversation.call_args[0]
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert SlackV3.kick_users_from_conversation.call_count == 1
    assert success_results[0] == 'Successfully kicked users from the channel.'
    assert send_args[0] == 'GKQ86DVPH'
    assert send_args[1] == ['U012A3CDE', 'U07QCRPA4']


def test_kick_users_no_channel_doesnt_exist(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'users': 'spengler, glinda'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '777'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'GKQ86DVPH'})
    mocker.patch.object(SlackV3, 'invite_users_to_conversation')
    mocker.patch.object(demisto, 'results')

    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.kick_from_channel()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert SlackV3.invite_users_to_conversation.call_count == 0
    assert err_msg == 'The channel was not found. Either the Slack app is not a member of the channel, or the slack app ' \
                      'does not have permission to find the channel.'


def test_rename_channel(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'channel': 'general', 'name': 'ey'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.rename_channel()

    send_args = slack_sdk.WebClient.api_call.call_args
    success_results = demisto.results.call_args[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 1
    assert slack_sdk.WebClient.api_call.call_count == 1
    assert success_results[0] == 'Channel renamed successfully.'
    assert send_args[0][0] == 'conversations.rename'
    assert send_args[1]['json']['channel'] == 'C012AB3CD'
    assert send_args[1]['json']['name'] == 'ey'


def test_rename_no_args_investigation(mocker):
    import SlackV3

    # Set

    new_mirror = {
        'channel_id': 'GKQ86DVPH',
        'channel_name': 'ey',
        'channel_topic': 'incident-681',
        'investigation_id': '681',
        'mirror_type': 'all',
        'mirror_direction': 'both',
        'mirror_to': 'group',
        'auto_close': True,
        'mirrored': True
    }

    mocker.patch.object(demisto, 'args', return_value={'name': 'ey'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '681'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')

    # Arrange
    SlackV3.rename_channel()

    send_args = slack_sdk.WebClient.api_call.call_args
    success_results = demisto.results.call_args[0]

    new_context = demisto.setIntegrationContext.call_args[0][0]
    new_mirrors = js.loads(new_context['mirrors'])
    our_mirror_filter = list(filter(lambda m: '681' == m['investigation_id'], new_mirrors))
    our_mirror = our_mirror_filter[0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert slack_sdk.WebClient.api_call.call_count == 1
    assert success_results[0] == 'Channel renamed successfully.'
    assert send_args[0][0] == 'conversations.rename'
    assert send_args[1]['json']['channel'] == 'GKQ86DVPH'
    assert send_args[1]['json']['name'] == 'ey'
    assert new_mirror == our_mirror


def test_rename_no_args_no_investigation(mocker):
    import SlackV3

    # Set

    mocker.patch.object(demisto, 'args', return_value={'name': 'ey'})
    mocker.patch.object(demisto, 'investigation', return_value={'id': '9999'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(SlackV3, 'get_conversation_by_name', return_value={'id': 'C012AB3CD'})
    mocker.patch.object(slack_sdk.WebClient, 'api_call')
    mocker.patch.object(demisto, 'results')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.rename_channel()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert SlackV3.get_conversation_by_name.call_count == 0
    assert err_msg == 'The channel was not found. Either the Slack app is not a member of the channel, or the slack app ' \
                      'does not have permission to find the channel.'


def test_get_user(mocker):
    from SlackV3 import get_user

    # Set

    mocker.patch.object(demisto, 'args', return_value={'user': 'spengler'})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(demisto, 'results')

    # Arrange

    get_user()
    user_results = demisto.results.call_args[0]

    assert user_results[0]['EntryContext'] == {'Slack.User(val.ID === obj.ID)': {
        'ID': 'U012A3CDE',
        'Username': 'spengler',
        'Name': 'Egon Spengler',
        'DisplayName': 'spengler',
        'Email': 'spengler@ghostbusters.example.com',
    }}


def test_get_user_by_name_paging_rate_limit(mocker):
    import SlackV3
    from slack_sdk.errors import SlackApiError
    from slack_sdk.web.slack_response import SlackResponse
    import time

    # Set
    SlackV3.init_globals()
    SlackV3.DISABLE_CACHING = False
    err_response: SlackResponse = SlackResponse(api_url='', client=None, http_verb='GET', req_args={},
                                                data={'ok': False}, status_code=429, headers={'Retry-After': 30})
    first_call = {'members': js.loads(USERS), 'response_metadata': {'next_cursor': 'dGVhbTpDQ0M3UENUTks='}}
    second_call = SlackApiError('Rate limit reached!', err_response)
    third_call = {'members': [{'id': 'U248918AB', 'name': 'alexios'}], 'response_metadata': {'next_cursor': ''}}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=[first_call, second_call, third_call])
    mocker.patch.object(time, 'sleep')

    # Arrange
    user = SlackV3.get_user_by_name('alexios')
    args = slack_sdk.WebClient.api_call.call_args_list
    first_args = args[0][1]
    second_args = args[2][1]

    # Assert
    assert len(first_args['params']) == 1
    assert first_args['params']['limit'] == 200
    assert len(second_args['params']) == 2
    assert second_args['params']['cursor'] == 'dGVhbTpDQ0M3UENUTks='
    assert user['id'] == 'U248918AB'
    assert slack_sdk.WebClient.api_call.call_count == 3


def test_get_user_by_name_paging_rate_limit_error(mocker):
    import SlackV3
    from slack_sdk.errors import SlackApiError
    from slack_sdk.web.slack_response import SlackResponse
    import time

    # Set
    SlackV3.init_globals()
    SlackV3.DISABLE_CACHING = False
    err_response: SlackResponse = SlackResponse(api_url='', client=None, http_verb='GET', req_args={},
                                                data={'ok': False}, status_code=429, headers={'Retry-After': 40})
    first_call = {'members': js.loads(USERS), 'response_metadata': {'next_cursor': 'dGVhbTpDQ0M3UENUTks='}}
    second_call = SlackApiError('Rate limit reached!', err_response)
    third_call = {'members': [{'id': 'U248918AB', 'name': 'alexios'}], 'response_metadata': {'next_cursor': ''}}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=[first_call, second_call, second_call, third_call])
    mocker.patch.object(time, 'sleep')

    # Arrange
    with pytest.raises(SlackApiError):
        SlackV3.get_user_by_name('alexios')
    args = slack_sdk.WebClient.api_call.call_args_list
    first_args = args[0][1]

    # Assert
    assert len(first_args['params']) == 1
    assert first_args['params']['limit'] == 200
    assert slack_sdk.WebClient.api_call.call_count == 3


def test_get_user_by_name_paging_normal_error(mocker):
    import SlackV3
    from slack_sdk.errors import SlackApiError
    from slack_sdk.web.slack_response import SlackResponse

    # Set
    SlackV3.init_globals()
    SlackV3.DISABLE_CACHING = False
    err_response: SlackResponse = SlackResponse(api_url='', client=None, http_verb='GET', req_args={},
                                                data={'ok': False}, status_code=500, headers={})
    first_call = {'members': js.loads(USERS), 'response_metadata': {'next_cursor': 'dGVhbTpDQ0M3UENUTks='}}
    second_call = SlackApiError('Whoops!', err_response)
    third_call = {'members': [{'id': 'U248918AB', 'name': 'alexios'}], 'response_metadata': {'next_cursor': ''}}

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=[first_call, second_call, third_call])

    # Arrange
    with pytest.raises(SlackApiError):
        SlackV3.get_user_by_name('alexios')
    args = slack_sdk.WebClient.api_call.call_args_list
    first_args = args[0][1]

    # Assert
    assert len(first_args['params']) == 1
    assert first_args['params']['limit'] == 200
    assert slack_sdk.WebClient.api_call.call_count == 2


def test_message_setting_name_and_icon(mocker):
    from SlackV3 import send_slack_request_sync, init_globals

    mocker.patch.object(demisto, 'params', return_value={'bot_name': 'kassandra', 'bot_icon': 'coolimage'})

    init_globals()

    # Set
    mocker.patch.object(slack_sdk.WebClient, 'api_call')

    # Arrange
    send_slack_request_sync(slack_sdk.WebClient, 'chat.postMessage', body={'channel': 'c', 'text': 't'})
    send_args = slack_sdk.WebClient.api_call.call_args[1]

    # Assert
    assert 'username' in send_args['json']
    assert 'icon_url' in send_args['json']


def test_message_not_setting_name_and_icon(mocker):
    from SlackV3 import send_slack_request_sync, init_globals

    mocker.patch.object(demisto, 'params', return_value={'bot_name': 'kassandra', 'bot_icon': 'coolimage'})

    init_globals()

    # Set
    mocker.patch.object(slack_sdk.WebClient, 'api_call')

    # Arrange
    send_slack_request_sync(slack_sdk.WebClient, 'conversations.setTopic', body={'channel': 'c', 'topic': 't'})
    send_args = slack_sdk.WebClient.api_call.call_args[1]

    # Assert
    assert 'username' not in send_args['json']
    assert 'icon_url' not in send_args['json']


@pytest.mark.asyncio
async def test_message_setting_name_and_icon_async(mocker):
    from SlackV3 import send_slack_request_async, init_globals

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        return

    mocker.patch.object(demisto, 'params', return_value={'bot_name': 'kassandra', 'bot_icon': 'coolimage'})

    init_globals()

    socket_client = AsyncMock()
    mocker.patch.object(socket_client.web_client, 'api_call', side_effect=api_call)

    # Arrange
    await send_slack_request_async(socket_client, 'chat.postMessage', body={'channel': 'c', 'text': 't'})
    send_args = socket_client.api_call.call_args[1]

    # Assert
    assert 'username' in send_args['json']
    assert 'icon_url' in send_args['json']


@pytest.mark.asyncio
async def test_message_not_setting_name_and_icon_async(mocker):
    from SlackV3 import send_slack_request_async, init_globals

    # Set
    async def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        return

    mocker.patch.object(demisto, 'params', return_value={'bot_name': 'kassandra', 'bot_icon': 'coolimage'})

    init_globals()

    socket_client = AsyncMock()
    mocker.patch.object(socket_client.web_client, 'api_call', side_effect=api_call)

    # Arrange
    await send_slack_request_async(socket_client, 'conversations.setTopic', body={'channel': 'c', 'topic': 't'})
    send_args = socket_client.api_call.call_args[1]

    # Assert
    assert 'username' not in send_args['json']
    assert 'icon_url' not in send_args['json']


def test_set_proxy_and_ssl(mocker):
    import SlackV3
    import ssl

    # Set
    mocker.patch.object(demisto, 'params', return_value={'unsecure': 'true', 'proxy': 'true'})
    mocker.patch.object(slack_sdk, 'WebClient')
    mocker.patch.object(SlackV3, 'handle_proxy', return_value={'https': 'https_proxy', 'http': 'http_proxy'})

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Arrange
    SlackV3.init_globals()
    init_args = slack_sdk.WebClient.call_args[1]
    assert init_args['ssl'].check_hostname is False
    assert init_args['ssl'].verify_mode == ssl.CERT_NONE
    assert init_args['proxy'] == 'http_proxy'


def test_set_proxy_by_url(mocker):
    import SlackV3
    import ssl

    # Set
    mocker.patch.object(demisto, 'params', return_value={'unsecure': 'true', 'proxy': 'true'})
    mocker.patch.object(slack_sdk, 'WebClient')
    mocker.patch.object(SlackV3, 'handle_proxy', return_value={'https': 'https_proxy', 'http': 'http_proxy'})

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Arrange
    SlackV3.init_globals()
    init_args = slack_sdk.WebClient.call_args[1]
    assert init_args['ssl'].check_hostname is False
    assert init_args['ssl'].verify_mode == ssl.CERT_NONE
    assert init_args['proxy'] == 'http_proxy'


def test_unset_proxy_and_ssl(mocker):
    from SlackV3 import init_globals

    # Set
    mocker.patch.object(slack_sdk, 'WebClient')

    # Arrange
    init_globals()
    init_args = slack_sdk.WebClient.call_args[1]
    assert init_args['ssl'] is None
    assert init_args['proxy'] is None


def test_fail_connect_threads(mocker):
    import SlackV3
    mocker.patch.object(demisto, 'params', return_value={'unsecure': 'true', 'bot_token': '123'})
    mocker.patch.object(demisto, 'args', return_value={'to': 'test', 'message': 'test message'})
    mocker.patch.object(demisto, 'command', return_value='send-notification')
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET)
    for i in range(8):
        SlackV3.main()
        time.sleep(0.5)
    assert return_error_mock.call_count == 8
    assert threading.active_count() < 6  # we shouldn't have more than 5 threads (1 + 4 max size of executor)


def test_slack_send_filter_one_mirror_tag(mocker):
    # When filtered_tags parameter contains the same tag as the entry tag - slack_send method should send the message
    import SlackV3

    mocker.patch.object(demisto, 'results')
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'slack_send_request', return_value=SLACK_RESPONSE_2)

    mocker.patch.object(demisto, 'args', return_value={'to': 'demisto', 'messageType': 'mirrorEntry',
                                                       'entryObject': {'tags': ['tag1']}})

    mocker.patch.object(demisto, 'params', return_value={'filtered_tags': 'tag1'})
    SlackV3.slack_send()
    assert demisto.results.mock_calls[0][1][0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: None'


def test_slack_send_filter_no_mirror_tags(mocker):
    # When filtered_tags parameter is empty slack_send method should send the message
    import SlackV3

    mocker.patch.object(demisto, 'results')
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'slack_send_request', return_value=SLACK_RESPONSE_2)

    mocker.patch.object(demisto, 'args', return_value={'to': 'demisto', 'messageType': 'mirrorEntry',
                                                       'entryObject': {'tags': ['tag1']}})

    mocker.patch.object(demisto, 'params', return_value={'filtered_tags': ''})
    SlackV3.slack_send()
    assert demisto.results.mock_calls[0][1][0]['HumanReadable'] == 'Message sent to Slack successfully.\nThread ID is: None'


def test_slack_send_filter_no_entry_tags(mocker):
    # When filtered_tags parameter contains one tag to filter messages and the entry have no tags -
    # slack_send method should exit and demisto.results.mock_calls should be empty
    import SlackV3

    mocker.patch.object(demisto, 'results')
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'slack_send_request', return_value={'cool': 'cool'})

    mocker.patch.object(demisto, 'args', return_value={'to': 'demisto', 'messageType': 'mirrorEntry',
                                                       'entryObject': {'tags': []}})

    mocker.patch.object(demisto, 'params', return_value={'filtered_tags': 'tag1'})
    SlackV3.slack_send()
    assert demisto.results.mock_calls == []


def test_handle_tags_in_message_sync(mocker):
    from SlackV3 import handle_tags_in_message_sync

    # Set
    def api_call(method: str, http_verb: str = 'POST', file: str = None, params=None, json=None, data=None):
        if method == 'users.list':
            return {'members': js.loads(USERS)}
        return None

    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(demisto, 'setIntegrationContext', side_effect=set_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)

    user_exists_message = 'Hello <@spengler>!'
    user_exists_message_in_email = "Hello <@spengler>! connected with spengler@ghostbusters.example.com !"
    user_doesnt_exist_message = 'Goodbye <@PetahTikva>!'

    user_message_exists_result = handle_tags_in_message_sync(user_exists_message)
    user_message_exists_in_email_result = handle_tags_in_message_sync(user_exists_message_in_email)
    user_message_doesnt_exist_result = handle_tags_in_message_sync(user_doesnt_exist_message)

    # Assert

    assert user_message_exists_result == 'Hello <@U012A3CDE>!'
    assert user_message_exists_in_email_result == 'Hello <@U012A3CDE>! connected with spengler@ghostbusters.example.com !'
    assert user_message_doesnt_exist_result == 'Goodbye PetahTikva!'


def test_send_message_to_destinations_non_strict():
    """
    Given:
        Blocks with non-strict json

    When:
        Sending message

    Then:
        No error is raised
    """
    from SlackV3 import send_message_to_destinations
    blocks = """[
                  {
                      "type": "section",
                      "text": {
                          "type": "mrkdwn",
                          "text": "*<${incident.siemlink}|${incident.name}>*\n${incident.details}"
                      }
                  },
                  {
                      "type": "section",
                      "fields": [
                          {
                              "type": "mrkdwn",
                              "text": "*Account ID:*\n${incident.accountid} "
                          }
                      ]
                  },
                  {
                      "type": "actions",
                      "elements": [
                          {
                              "type": "button",
                              "text": {
                                  "type": "plain_text",
                                  "text": "Acknowledge"
                              },
                              "value": "ack"
                          }
                      ]
                  }
              ]"""
    send_message_to_destinations([], "", "", blocks=blocks)  # No destinations, no response


@pytest.mark.parametrize('sent, expected_minutes', [(None, 1), ('2019-09-26 18:37:25', 1), ('2019-09-26 18:10:25', 2),
                                                    ('2019-09-26 17:38:24', 5), ('2019-09-25 18:10:25', 5)])
def test_get_poll_minutes(sent, expected_minutes):
    from SlackV3 import get_poll_minutes

    # Set
    current = datetime.datetime(2019, 9, 26, 18, 38, 25)

    # Arrange
    minutes = get_poll_minutes(current, sent)

    # Assert
    assert minutes == expected_minutes


def test_edit_message(mocker):
    """
    Given:
        The text 'Boom', a threadID and known channel.

    When:
        Editing a message

    Then:
        Send a request to slack where the text includes the url footer, and valid channel ID.
    """
    import SlackV3
    # Set

    slack_response_mock = SlackResponse(
        client=None,
        http_verb='',
        api_url='',
        req_args={},
        headers={},
        status_code=200,
        data={
            'ok': True,
            'channel': 'C061EG9T2',
            'ts': '1629281551.001000',
            'text': 'Boom\nView it on: <https://www.eizelulz.com:8443/#/WarRoom/727>',
            'message': {
                'type': 'message',
                'subtype': 'bot_message',
                'text': 'Boom\nView it on: <https://www.eizelulz.com:8443/#/WarRoom/727>',
                'username': 'Cortex XSOAR',
                'icons': {
                    'image_48': 'https://s3-us-west-2.amazonaws.com/slack-files2/bot_icons/2021-06-29/2227534346388_48.png'
                },
                'bot_id': 'B01UZHGMQ9G'
            }
        }
    )

    expected_body = {
        'body': {
            'channel': 'C061EG9T2',
            'ts': '1629281551.001000',
            'text': 'Boom\nView it on: https://www.eizelulz.com:8443/#/WarRoom/727'
        }
    }

    link = 'https://www.eizelulz.com:8443/#/WarRoom/727'
    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'demistoUrls', return_value={'warRoom': link})
    mocker.patch.object(demisto, 'args', return_value={'channel': "random", "threadID": "1629281551.001000", "message": "Boom"})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'send_slack_request_sync', return_value=slack_response_mock)

    # Arrange
    SlackV3.slack_edit_message()

    args = SlackV3.send_slack_request_sync.call_args.kwargs

    # Assert
    assert SlackV3.send_slack_request_sync.call_count == 1

    assert args == expected_body


def test_edit_message_not_valid_thread_id(mocker):
    """
    Given:
        The text 'Boom', an incorrect threadID and known channel.

    When:
        Editing a message

    Then:
        Send a request to slack where the text includes the url footer, and valid channel ID.
    """
    import SlackV3
    # Set

    err_response: SlackResponse = SlackResponse(api_url='', client=None, http_verb='POST',
                                                req_args={},
                                                data={'ok': False, 'error': 'message_not_found'},
                                                status_code=429,
                                                headers={})
    api_call = SlackApiError('The request to the Slack API failed.', err_response)

    expected_body = ('The request to the Slack API failed.\n'"The server responded with: {'ok': "
                     "False, 'error': 'message_not_found'}")

    link = 'https://www.eizelulz.com:8443/#/WarRoom/727'
    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'demistoUrls', return_value={'warRoom': link})
    mocker.patch.object(demisto, 'args', return_value={'channel': "random", "threadID": "162928", "message": "Boom"})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.slack_edit_message()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert err_msg == expected_body


def test_pin_message(mocker):
    """
     Given:
        The a valid threadID and known channel.

    When:
        Pinning a message

    Then:
        Send a request to slack where message is successfully pinned.
    """
    import SlackV3
    # Set

    slack_response_mock = {
        'ok': True
    }

    expected_body = {
        'body': {
            'channel': 'C061EG9T2',
            'timestamp': '1629281551.001000'
        }
    }

    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'args', return_value={'channel': "random", "threadID": "1629281551.001000"})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(SlackV3, 'send_slack_request_sync', return_value=slack_response_mock)

    # Arrange
    SlackV3.pin_message()

    args = SlackV3.send_slack_request_sync.call_args.kwargs

    # Assert
    assert SlackV3.send_slack_request_sync.call_count == 1

    assert args == expected_body


def test_pin_message_invalid_thread_id(mocker):
    """
     Given:
        The an invalid threadID and known channel.

    When:
        Pinning a message.

    Then:
        Send a request to slack where an error message is returned indicating the message could not
        be found.
    """
    import SlackV3
    # Set

    err_response: SlackResponse = SlackResponse(api_url='', client=None, http_verb='POST',
                                                req_args={},
                                                data={'ok': False, 'error': 'message_not_found'},
                                                status_code=429,
                                                headers={})
    api_call = SlackApiError('The request to the Slack API failed.', err_response)

    expected_body = (
        'The request to the Slack API failed.\n'"The server responded with: {'ok': False, "
        "'error': 'message_not_found'}")

    mocker.patch.object(demisto, 'investigation', return_value={'type': 1})
    mocker.patch.object(demisto, 'args', return_value={'channel': "random", "threadID": "1629281551.001000"})
    mocker.patch.object(demisto, 'getIntegrationContext', side_effect=get_integration_context)
    mocker.patch.object(slack_sdk.WebClient, 'api_call', side_effect=api_call)
    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=InterruptedError())

    # Arrange
    with pytest.raises(InterruptedError):
        SlackV3.pin_message()

    err_msg = return_error_mock.call_args[0][0]

    # Assert
    assert err_msg == expected_body
