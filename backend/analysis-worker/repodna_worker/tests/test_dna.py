from repodna_worker.scoring.dna import calculate_dna_scores


def test_perfect_scores():
    files = [
        {
            "path": "services/UserService.py",
            "functions": [
                {
                    "name": "get_user",
                    "complexity": 1,
                    "loc": 20,
                }
            ],
        }
    ]

    graph = {
        "edges": [],
    }

    architecture = {
        "violations": [],
    }

    cycles = []

    result = calculate_dna_scores(
        files=files,
        graph=graph,
        architecture=architecture,
        cycles=cycles,
    )

    assert result == {
        "architecture": 100.0,
        "code": 100.0,
        "quality": 100.0,
    }


def test_architecture_score_with_violations_and_cycles():
    architecture = {
        "violations": [
            {
                "from": "controllers/UserController.py",
                "to": "repositories/UserRepository.py",
                "rule": "controller_to_repository",
            },
            {
                "from": "repositories/UserRepository.py",
                "to": "services/UserService.py",
                "rule": "repository_to_service",
            },
        ],
    }

    cycles = [
        ["A.py", "B.py"],
    ]

    result = calculate_dna_scores(
        files=[],
        graph={},
        architecture=architecture,
        cycles=cycles,
    )

    # Layer adherence = 100 - (2 * 10) = 80
    # Cycle health = 100 - (1 * 15) = 85
    # Architecture = 0.70*80 + 0.30*85 = 81.5

    assert result["architecture"] == 81.5


def test_code_score():
    files = [
        {
            "path": "services/UserService.py",
            "functions": [
                {
                    "name": "small_function",
                    "complexity": 1,
                    "loc": 20,
                },
                {
                    "name": "complex_function",
                    "complexity": 11,
                    "loc": 120,
                },
            ],
        }
    ]

    result = calculate_dna_scores(
        files=files,
        graph={},
        architecture={},
        cycles=[],
    )

    # Average complexity = (1 + 11) / 2 = 6
    # complexity score = 100 - (6 - 1) * 10 = 50
    #
    # 1 of 2 functions is over complexity 10
    # threshold score = 100 - 50 = 50
    #
    # max function size = 120
    # size score = 100 - (120 - 100) = 80
    #
    # Code DNA = 0.40*50 + 0.30*50 + 0.30*80
    #          = 20 + 15 + 24
    #          = 59

    assert result["code"] == 59.0


def test_quality_score():
    graph = {
        "edges": [
            {
                "source": "A.py",
                "target": "B.py",
            },
            {
                "source": "A.py",
                "target": "C.py",
        }
        ],
    }

    result = calculate_dna_scores(
        files=[],
        graph=graph,
        architecture={},
        cycles=[],
    )

    # Nodes = A, B, C
    # A fan-out = 2
    # B fan-out = 0
    # C fan-out = 0
    #
    # Average fan-out = 2 / 3
    #
    # coupling score = 100 - (2/3 * 10)
    #                = 93.333...
    #
    # No cycles => cycle score = 100
    #
    # No node has fan-out > 5
    # hotspot score = 100
    #
    # Quality =
    # 0.40*93.333... + 0.30*100 + 0.30*100
    # = 97.333...

    assert result["quality"] == 97.33


def test_scores_are_clamped_to_zero():
    architecture = {
        "violations": [
            {"rule": "violation"} for _ in range(20)
        ],
    }

    cycles = [
        ["A", "B"]
        for _ in range(20)
    ]

    result = calculate_dna_scores(
        files=[],
        graph={},
        architecture=architecture,
        cycles=cycles,
    )

    assert result["architecture"] == 0.0


def test_empty_inputs_return_perfect_scores():
    result = calculate_dna_scores()

    assert result == {
        "architecture": 100.0,
        "code": 100.0,
        "quality": 100.0,
    }


def test_deterministic_output():
    files = [
        {
            "path": "services/UserService.py",
            "functions": [
                {
                    "name": "get_user",
                    "complexity": 4,
                    "loc": 30,
                },
                {
                    "name": "save_user",
                    "complexity": 7,
                    "loc": 50,
                },
            ],
        }
    ]

    graph = {
        "edges": [
            {
                "source": "controllers/UserController.py",
                "target": "services/UserService.py",
            },
            {
                "source": "services/UserService.py",
                "target": "repositories/UserRepository.py",
            },
        ],
    }

    architecture = {
        "violations": [],
    }

    cycles = []

    first = calculate_dna_scores(
        files=files,
        graph=graph,
        architecture=architecture,
        cycles=cycles,
    )

    second = calculate_dna_scores(
        files=files,
        graph=graph,
        architecture=architecture,
        cycles=cycles,
    )

    assert first == second


def test_score_dna_alias():
    from repodna_worker.scoring.dna import score_dna

    first = calculate_dna_scores(
        files=[],
        graph={},
        architecture={},
        cycles=[],
    )

    second = score_dna(
        files=[],
        graph={},
        architecture={},
        cycles=[],
    )

    assert first == second