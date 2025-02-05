import pytest

from itou.utils.apis.data_inclusion import DataInclusionApiClient, DataInclusionApiException


def test_data_inclusion_client(settings, respx_mock):
    client = DataInclusionApiClient("https://fake.api.gouv.fr/", "fake-token")
    settings.API_DATA_INCLUSION_SOURCES = "dora,toto"
    api_mock = respx_mock.get("https://fake.api.gouv.fr/search/services")
    api_mock.respond(
        200,
        json={
            "items": [
                {"service": {"id": "svc1"}, "distance": 1},
                {"service": {"id": "svc2"}, "distance": 3},
                {"service": {"id": "svc3"}, "distance": 2},
                {"service": {"id": "svc4"}, "distance": 5},
            ]
        },
    )

    assert client.services("fake-insee-code") == [{"id": "svc1"}, {"id": "svc2"}, {"id": "svc3"}, {"id": "svc4"}]
    from urllib.parse import parse_qs

    assert parse_qs(str(api_mock.calls[0].request.url.params)) == {
        "code_insee": ["fake-insee-code"],
        "sources": ["dora,toto"],
        "thematiques": [
            "acces-aux-droits-et-citoyennete",
            "accompagnement-social-et-professionnel-personnalise",
            "apprendre-francais",
            "choisir-un-metier",
            "mobilite",
            "trouver-un-emploi",
        ],
    }
    assert api_mock.calls[0].request.headers["authorization"] == "Bearer fake-token"

    # check exceptions
    api_mock.respond(200, json={"something": "else"})
    with pytest.raises(DataInclusionApiException):
        client.services("fake-insee-code")

    api_mock.respond(403, json={"something": "else"})
    with pytest.raises(DataInclusionApiException):
        client.services("fake-insee-code")
