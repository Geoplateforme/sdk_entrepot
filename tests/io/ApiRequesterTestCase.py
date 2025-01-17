from http import HTTPStatus
from io import BufferedReader
import json
from pathlib import Path
from typing import Dict, Tuple
from unittest.mock import MagicMock, patch, mock_open
import requests
import requests_mock

from sdk_entrepot_gpf.io.Config import Config
from sdk_entrepot_gpf.Errors import GpfSdkError
from sdk_entrepot_gpf.auth.Authentifier import Authentifier
from sdk_entrepot_gpf.io.ApiRequester import ApiRequester
from sdk_entrepot_gpf.io.Errors import NotFoundError, RouteNotFoundError, ConflictError
from tests.GpfTestCase import GpfTestCase

# pylint:disable=protected-access


class ApiRequesterTestCase(GpfTestCase):
    """Tests ApiRequester class.

    cmd : python3 -m unittest -b tests.io.ApiRequesterTestCase
    """

    # On va mocker la classe d'authentification globalement
    o_mock_authentifier = patch.object(Authentifier, "get_access_token_string", return_value="test_token")

    # Paramètres de requêtes
    url = "https://api.test.io/"
    param = {
        "param_key_1": "value_1",
        "param_key_2": 2,
        "param_keys[]": ["pk1", "pk2", "pk3"],
    }
    encoded_param = "?param_key_1=value_1&param_key_2=2&param_keys%5B%5D=pk1&param_keys%5B%5D=pk2&param_keys%5B%5D=pk3"
    data = {
        "data_key_1": "value_1",
        "data_key_2": 2,
    }
    files: Dict[str, Tuple[str, BufferedReader]] = {}
    response = {"key": "value"}

    @classmethod
    def setUpClass(cls) -> None:
        """fonction lancée une fois avant tous les tests de la classe"""
        super().setUpClass()
        # On détruit le Singleton Config
        Config._instance = None
        # On charge une config spéciale pour les tests d'authentification
        o_config = Config()
        o_config.read(GpfTestCase.conf_dir_path / "test_requester.ini")
        # On mock la classe d'authentification
        cls.o_mock_authentifier.start()

    @classmethod
    def tearDownClass(cls) -> None:
        """fonction lancée une fois après tous les tests de la classe"""
        super().tearDownClass()
        # On ne mock plus la classe d'authentification
        cls.o_mock_authentifier.stop()
        # On détruit le Singleton Config
        Config._instance = None

    def test_route_request_ok_datastore_config(self) -> None:
        """Test de route_request quand la route existe en utilisant le datastore de base."""
        # Instanciation d'une fausse réponse HTTP
        o_api_response = GpfTestCase.get_response()
        # On mock la fonction url_request, on veut vérifier qu'elle est appelée avec les bons param
        with patch.object(ApiRequester(), "url_request", return_value=o_api_response) as o_mock_request:
            # On effectue une requête
            o_fct_response = ApiRequester().route_request(
                "test_create",
                {"id": 42},
                ApiRequester.POST,
                params=self.param,
                data=self.data,
                files=self.files,
            )
            # Vérification sur o_mock_request
            s_url = "https://api.test.io/api/v1/datastores/TEST_DATASTORE/create/42"
            o_mock_request.assert_called_once_with(s_url, ApiRequester.POST, self.param, self.data, self.files, {}, -1000)
            # Vérification sur la réponse renvoyée par la fonction : ça doit être celle renvoyée par url_request
            self.assertEqual(o_fct_response, o_api_response)

    def test_route_request_timeout(self) -> None:
        """Test de route_request quand la route existe pour le timeout."""
        # Instanciation d'une fausse réponse HTTP
        o_api_response = GpfTestCase.get_response()
        # timeout dans la requête
        with patch.object(ApiRequester(), "url_request", return_value=o_api_response) as o_mock_request:
            # On effectue une requête
            o_fct_response = ApiRequester().route_request(
                "test_timeout",
                {"id": 42},
                ApiRequester.POST,
                params=self.param,
                data=self.data,
                files=self.files,
                timeout=40,
            )
            # Vérification sur o_mock_request
            s_url = "https://api.test.io/api/v1/datastores/TEST_DATASTORE/timeout/42"
            o_mock_request.assert_called_once_with(s_url, ApiRequester.POST, self.param, self.data, self.files, {}, 40)
            # Vérification sur la réponse renvoyée par la fonction : ça doit être celle renvoyée par url_request
            self.assertEqual(o_fct_response, o_api_response)
        # timeout pour la route
        with patch.object(ApiRequester(), "url_request", return_value=o_api_response) as o_mock_request:
            # On effectue une requête
            o_fct_response = ApiRequester().route_request(
                "test_timeout",
                {"id": 42},
                ApiRequester.POST,
                params=self.param,
                data=self.data,
                files=self.files,
            )
            # Vérification sur o_mock_request
            s_url = "https://api.test.io/api/v1/datastores/TEST_DATASTORE/timeout/42"
            o_mock_request.assert_called_once_with(s_url, ApiRequester.POST, self.param, self.data, self.files, {}, 50)
            # Vérification sur la réponse renvoyée par la fonction : ça doit être celle renvoyée par url_request
            self.assertEqual(o_fct_response, o_api_response)

    def test_route_request_ok_datastore_params(self) -> None:
        """Test de route_request quand la route existe en surchargeant le datastore."""
        # Instanciation d'une fausse réponse HTTP
        o_api_response = GpfTestCase.get_response()
        # On mock la fonction url_request, on veut vérifier qu'elle est appelée avec les bons param
        with patch.object(ApiRequester(), "url_request", return_value=o_api_response) as o_mock_request:
            # On effectue une requête
            o_fct_response = ApiRequester().route_request(
                "test_create",
                {"id": 42, "datastore": "OTHER_DATASTORE"},
                ApiRequester.POST,
                params=self.param,
                data=self.data,
                files=self.files,
            )
            # Vérification sur o_mock_request
            s_url = "https://api.test.io/api/v1/datastores/OTHER_DATASTORE/create/42"
            o_mock_request.assert_called_once_with(s_url, ApiRequester.POST, self.param, self.data, self.files, {}, -1000)
            # Vérification sur la réponse renvoyée par la fonction : ça doit être celle renvoyée par url_request
            self.assertEqual(o_fct_response, o_api_response)

    def test_route_request_ko(self) -> None:
        """Test de route_request quand la route n'existe pas."""
        # On veut vérifier que l'exception RouteNotFoundError est levée avec le bon nom de route non trouvée
        with self.assertRaises(RouteNotFoundError) as o_arc:
            # On effectue une requête
            ApiRequester().route_request("non_existing")
        # Vérifications
        self.assertEqual(o_arc.exception.route_name, "non_existing")

    def test_url_request_get(self) -> None:
        """Test de url_request dans le cadre d'une requête get."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            # Une requête réussie
            o_mock.get(self.url, json=self.response)
            # On effectue une requête
            o_response = ApiRequester().url_request(self.url, ApiRequester.GET, params=self.param, data=self.data)
            # Vérification sur la réponse
            self.assertDictEqual(o_response.json(), self.response)
            # On a dû faire une requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")
            # Vérifications sur l'historique (enfin ici y'a une requête...)
            o_history = o_mock.request_history
            # Requête 1 : vérification de l'url
            self.assertEqual(o_history[0].url, self.url + self.encoded_param, "check url")
            # Requête 1 : vérification du type
            self.assertEqual(o_history[0].method.lower(), "get", "method == get")
            # Requête 1 : vérification du corps de requête
            s_text = json.dumps(self.data)
            self.assertEqual(o_history[0].text, s_text, "check text")
            # Requête 1 : timeout valeur par défaut
            self.assertEqual(o_history[0].timeout, 600)

    def test_url_request_post(self) -> None:
        """Test de url_request dans le cadre d'une requête post."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            # Une requête réussie
            o_mock.post(self.url, json=self.response)
            # On effectue une requête
            o_response = ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
            # Vérification sur la réponse
            self.assertDictEqual(o_response.json(), self.response)
            # On a dû faire une requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")
            # Vérifications sur l'historique (enfin ici y'a une requête...)
            o_history = o_mock.request_history
            # Requête 1 : vérification de l'url
            self.assertEqual(o_history[0].url, self.url + self.encoded_param, "check url")
            # Requête 1 : vérification du type
            self.assertEqual(o_history[0].method.lower(), "post", "method == post")
            # Requête 1 : vérification du corps de requête
            s_text = json.dumps(self.data)
            self.assertEqual(o_history[0].text, s_text, "check text")
            # Requête 1 : timeout valeur par défaut
            self.assertEqual(o_history[0].timeout, 600, "timeout")

    def test_url_request_timeout_param(self) -> None:
        """Test de url_request pour les timeout."""
        # Timeout None
        with requests_mock.Mocker() as o_mock:
            # Une requête réussie
            o_mock.post(self.url, json=self.response)
            # On effectue une requête
            o_response = ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data, timeout=None)
            # Vérification sur la réponse
            self.assertDictEqual(o_response.json(), self.response)
            # On a dû faire une requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")
            # Vérifications sur l'historique (enfin ici y'a une requête...)
            o_history = o_mock.request_history
            # Requête 1 : vérification de l'url
            self.assertEqual(o_history[0].url, self.url + self.encoded_param, "check url")
            # Requête 1 : vérification du type
            self.assertEqual(o_history[0].method.lower(), "post", "method == post")
            # Requête 1 : vérification du corps de requête
            s_text = json.dumps(self.data)
            self.assertEqual(o_history[0].text, s_text, "check text")
            # Requête 1 : timeout
            self.assertEqual(o_history[0].timeout, None)
        # Timeout 10s
        with requests_mock.Mocker() as o_mock:
            # Une requête réussie
            o_mock.post(self.url, json=self.response)
            # On effectue une requête
            o_response = ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data, timeout=10)
            # Vérification sur la réponse
            self.assertDictEqual(o_response.json(), self.response)
            # On a dû faire une requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")
            # Vérifications sur l'historique (enfin ici y'a une requête...)
            o_history = o_mock.request_history
            # Requête 1 : vérification de l'url
            self.assertEqual(o_history[0].url, self.url + self.encoded_param, "check url")
            # Requête 1 : vérification du type
            self.assertEqual(o_history[0].method.lower(), "post", "method == post")
            # Requête 1 : vérification du corps de requête
            s_text = json.dumps(self.data)
            self.assertEqual(o_history[0].text, s_text, "check text")
            # Requête 1 : timeout
            self.assertEqual(o_history[0].timeout, 10)

    def test_url_request_internal_server_error(self) -> None:
        """Test de url_request dans le cadre de 3 erreurs internes de suite."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            # Une requête non réussie
            o_mock.post(self.url, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            # On s'attend à une exception
            with self.assertRaises(GpfSdkError) as o_arc:
                # On effectue une requête
                ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            self.assertEqual(o_arc.exception.message, "L'exécution d'une requête a échoué après 3 tentatives.")
            # On a dû faire 3 requêtes
            self.assertEqual(o_mock.call_count, 3, "o_mock.call_count == 3")

    def test_url_request_bad_request(self) -> None:
        """Test de url_request dans le cadre de 1 erreur bad request."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            # Une requête non réussie
            o_mock.post(self.url, status_code=HTTPStatus.BAD_REQUEST)
            # On s'attend à une exception
            with self.assertRaises(GpfSdkError) as o_arc:
                # On effectue une requête
                ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            self.assertEqual(o_arc.exception.message, "La requête formulée par le programme est incorrecte (Pas d'indication spécifique indiquée par l'API.). Contactez le support.")
            # On a dû faire 1 seule requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")

    def test_url_request_conflict(self) -> None:
        """Test de url_request dans le cadre de 1 erreur conflict."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            # Une requête non réussie
            o_mock.post(self.url, status_code=HTTPStatus.CONFLICT)
            # On s'attend à une exception
            with self.assertRaises(ConflictError):
                # On effectue une requête
                ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            # self.assertEqual(o_arc.exception.message, "La requête envoyée à l'Entrepôt génère un conflit. N'avez-vous pas déjà effectué l'action que vous essayez de faire ?")
            # Au contraire de GpfSdkError, ConflictError ne comporte pas de membre message...
            # On a dû faire 1 seule requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")

    def test_url_request_not_found(self) -> None:
        """Test de url_request dans le cadre d'une erreur 404 (not found)."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            # Une requête non réussie
            o_mock.post(self.url, status_code=HTTPStatus.NOT_FOUND)
            # On s'attend à une exception
            with self.assertRaises(NotFoundError):
                # On effectue une requête
                ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
            # On a dû faire 1 seule requête (sortie immédiate dans ce cas)
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")

    def test_url_request_not_authorized(self) -> None:
        """Test de url_request dans le cadre d'une erreur 403 ou 401 (not authorized)."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            with patch.object(Authentifier(), "revoke_token", return_value=None) as o_mock_revoke_token:
                # Une requête avec comme codes retour 104, 403 puis 200
                o_mock.post(
                    self.url,
                    [
                        {"status_code": HTTPStatus.UNAUTHORIZED},
                        {"status_code": HTTPStatus.FORBIDDEN},
                        {"status_code": HTTPStatus.OK},
                    ],
                )
                # Lancement de la requête
                ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
                # On a dû faire 3 requêtes
                self.assertEqual(o_mock.call_count, 3, "o_mock.call_count == 3")
                # On a dû faire 2 appels à revoke_token
                self.assertEqual(o_mock_revoke_token.call_count, 2, "o_mock_revoke_token.call_count == 2")

    def test_url_request_connection_error(self) -> None:
        """Test de url_request dans le cadre d'une erreur ConnectionError."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            o_mock.get(self.url, exc=requests.exceptions.ConnectionError)
            # On s'attend à une exception
            with self.assertRaises(GpfSdkError) as o_arc:
                # Lancement de la requête
                ApiRequester().url_request(self.url, ApiRequester.GET, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            self.assertEqual(
                o_arc.exception.message,
                f"Le serveur de l'API Entrepôt ({self.url}) n'est pas joignable. Cela peut être dû à un problème de configuration si elle a changé récemment."
                + " Sinon, c'est un problème sur l'API Entrepôt : consultez l'état du service pour en savoir plus "
                + f": {Config().get_str('store_api', 'check_status_url')}.",
            )
            # On a dû faire le max de requête
            self.assertEqual(o_mock.call_count, Config().get_int("store_api", "nb_attempts"), "o_mock.call_count == max")

    def test_url_request_http_error(self) -> None:
        """Test de url_request dans le cadre où on a une HTTPError."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            o_mock.get(self.url, exc=requests.HTTPError)
            # On s'attend à une exception
            with self.assertRaises(GpfSdkError) as o_arc:
                # Lancement de la requête
                ApiRequester().url_request(self.url, ApiRequester.GET, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            self.assertEqual(o_arc.exception.message, "L'URL indiquée en configuration est invalide ou inexistante. Contactez le support.")
            # On a dû faire 1 seule requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")

    def test_url_request_code_autre(self) -> None:
        """Test de url_request dans le cadre où on code retour non pris en charge."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            o_mock.post(self.url, status_code=1)
            # On s'attend à une exception
            with self.assertRaises(GpfSdkError) as o_arc:
                # Lancement de la requête
                ApiRequester().url_request(self.url, ApiRequester.POST, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            self.assertEqual(o_arc.exception.message, "L'exécution d'une requête a échoué après 3 tentatives.")
            # On a dû faire 1 seule requête
            self.assertEqual(o_mock.call_count, 3, "o_mock.call_count == 3")

    def test_url_request_url_required(self) -> None:
        """Test de url_request dans le cadre où on a une URLRequired."""
        # On mock...
        with requests_mock.Mocker() as o_mock:
            o_mock.get(self.url, exc=requests.URLRequired)
            # On s'attend à une exception
            with self.assertRaises(GpfSdkError) as o_arc:
                # Lancement de la requête
                ApiRequester().url_request(self.url, ApiRequester.GET, params=self.param, data=self.data)
            # On doit avoir un message d'erreur
            self.assertEqual(o_arc.exception.message, "L'URL indiquée en configuration est invalide ou inexistante. Contactez le support.")
            # On a dû faire 1 seule requête
            self.assertEqual(o_mock.call_count, 1, "o_mock.call_count == 1")

    def test_range_next_page(self) -> None:
        """Test de range_next_page."""
        # On a 10 entités à récupérer et on en a récupéré 10 : on ne doit pas continuer
        self.assertFalse(ApiRequester.range_next_page("1-10/10", 10))
        # On a 10 entités à récupérer et on en a récupéré 5 : on doit continuer
        self.assertTrue(ApiRequester.range_next_page("1-5/10", 5))
        # Content-Range nul : on doit s'arrêter
        self.assertFalse(ApiRequester.range_next_page(None, 5))
        # Content-Range non parsable : on doit s'arrêter
        self.assertFalse(ApiRequester.range_next_page("non_parsable", 0))

    def test_route_upload_file(self) -> None:
        """test de route_upload_file"""
        p_file = Path("rep/file")
        s_path_api = "key"
        s_route_name = "route_name"
        d_route_params = None
        s_method = "POST"
        d_params = None
        d_data = None

        o_open = mock_open()
        o_tuple_file = (p_file.name, o_open.return_value)
        o_dict_files = {s_path_api: o_tuple_file}
        o_mock_stat = MagicMock()
        o_mock_stat.st_size = 10
        # pas de timeout
        with patch.object(Path, "open", return_value=o_open.return_value) as o_mock_open:
            with patch.object(Path, "stat", return_value=o_mock_stat):
                with patch.object(ApiRequester, "route_request", return_value=None) as o_mock_request:
                    ApiRequester().route_upload_file(s_route_name, p_file, s_path_api, d_route_params, s_method, d_params, d_data)
                    o_mock_open.assert_called_once_with("rb")
                    o_mock_request.assert_called_once_with(s_route_name, route_params=d_route_params, method=s_method, params=d_params, data=d_data, files=o_dict_files, timeout=600)
        o_mock_stat.reset_mock()

        # timeout None
        for s_route_name in ["test_upload_none_1", "test_upload_none_2", "test_upload_none_3"]:
            with patch.object(Path, "open", return_value=o_open.return_value) as o_mock_open:
                with patch.object(Path, "stat", return_value=o_mock_stat):
                    with patch.object(ApiRequester, "route_request", return_value=None) as o_mock_request:
                        ApiRequester().route_upload_file(s_route_name, p_file, s_path_api, d_route_params, s_method, d_params, d_data)
                        o_mock_open.assert_called_once_with("rb")
                        o_mock_request.assert_called_once_with(s_route_name, route_params=d_route_params, method=s_method, params=d_params, data=d_data, files=o_dict_files, timeout=None)
            o_mock_stat.reset_mock()

        # timeout fixe
        s_route_name = "test_upload_fixe"
        with patch.object(Path, "open", return_value=o_open.return_value) as o_mock_open:
            with patch.object(Path, "stat", return_value=o_mock_stat):
                with patch.object(ApiRequester, "route_request", return_value=None) as o_mock_request:
                    ApiRequester().route_upload_file(s_route_name, p_file, s_path_api, d_route_params, s_method, d_params, d_data)
                    o_mock_open.assert_called_once_with("rb")
                    o_mock_request.assert_called_once_with(s_route_name, route_params=d_route_params, method=s_method, params=d_params, data=d_data, files=o_dict_files, timeout=60)
        o_mock_stat.reset_mock()

        # timeout selon taille du fichier
        s_route_name = "test_upload_variable"
        for i_taille_ficher, i_timeout in [(1, 600), (15, 15), (16, 15), (35, 30), (65, None), (70, 70), (700000, 70)]:
            o_mock_stat.st_size = i_taille_ficher
            with patch.object(Path, "open", return_value=o_open.return_value) as o_mock_open:
                with patch.object(Path, "stat", return_value=o_mock_stat):
                    with patch.object(ApiRequester, "route_request", return_value=None) as o_mock_request:
                        ApiRequester().route_upload_file(s_route_name, p_file, s_path_api, d_route_params, s_method, d_params, d_data)
                        o_mock_open.assert_called_once_with("rb")
                        o_mock_request.assert_called_once_with(s_route_name, route_params=d_route_params, method=s_method, params=d_params, data=d_data, files=o_dict_files, timeout=i_timeout)
            o_mock_stat.reset_mock()
