from repodna_worker.architecture.layers import classify_layer


def test_controller_folder():
    assert classify_layer("src/controller/UserController.py") == "controller"


def test_controller_filename():
    assert classify_layer("src/UserController.py") == "controller"


def test_service_folder():
    assert classify_layer("src/services/UserService.py") == "service"


def test_service_filename():
    assert classify_layer("src/UserService.py") == "service"


def test_repository_folder():
    assert classify_layer("src/repository/UserRepository.py") == "repository"


def test_repository_filename():
    assert classify_layer("src/UserRepository.py") == "repository"


def test_unknown_layer():
    assert classify_layer("src/utils/constants.py") == "unknown"


def test_case_insensitive():
    assert classify_layer("src/Controller/UserController.py") == "controller"