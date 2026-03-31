import asyncio
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    # Prefer the root OpenHands package over the legacy vendored copy in MopenHands.
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import toml
from datasets import load_dataset

import openhands.agenthub
from evaluation.benchmarks.swe_bench.resource.mapping import (
    get_instance_resource_factor,
)
from evaluation.utils.shared import (
    EvalException,
    EvalMetadata,
    EvalOutput,
    assert_and_raise,
    codeact_user_response,
    get_default_sandbox_config_for_eval,
    get_metrics,
    get_openhands_config_for_eval,
    is_fatal_evaluation_error,
    make_metadata,
    prepare_dataset,
    reset_logger_for_multiprocessing,
    run_evaluation,
    update_llm_config_for_completions_logging,
)
from openhands.controller.state.state import State
from openhands.core.config import (
    AgentConfig,
    OpenHandsConfig,
    get_llm_config_arg,
    get_evaluation_parser,
)
from openhands.core.logger import openhands_logger as logger
from openhands.core.main import create_runtime, run_controller
from openhands.events.action import CmdRunAction, MessageAction, FileReadAction
from openhands.events.observation import CmdOutputObservation, ErrorObservation
from openhands.events.serialization.event import event_to_dict
from openhands.runtime.base import Runtime
from openhands.utils.async_utils import call_async_from_sync
from openhands.utils.shutdown_listener import sleep_if_should_continue

USE_HINT_TEXT = os.environ.get('USE_HINT_TEXT', 'false').lower() == 'true'
USE_INSTANCE_IMAGE = os.environ.get('USE_INSTANCE_IMAGE', 'true').lower() == 'true'
RUN_WITH_BROWSING = os.environ.get('RUN_WITH_BROWSING', 'false').lower() == 'true'

# TODO: migrate all swe-bench docker to ghcr.io/openhands
# TODO: 适应所有的语言
DOCKER_IMAGE_PREFIX = os.environ.get('EVAL_DOCKER_IMAGE_PREFIX', '')
LANGUAGE =os.environ.get('LANGUAGE', 'python')
logger.info(f'Using docker image prefix: {DOCKER_IMAGE_PREFIX}')

# Files that are often generated during agent runs and should never be submitted
# as benchmark solution patches.
EXCLUDE_PATCH_PATHS = {
    'patch.diff',
    'test-output.log',
    'testlog.out',
    'run_test.sh',
    'reproduce_error.py',
}

EXCLUDE_PATCH_BASENAME_PATTERNS = (
    re.compile(r'reproduce.*\.py$'),
    re.compile(r'test_script.*\.py$'),
)


def _should_exclude_patch_path(path: str) -> bool:
    basename = os.path.basename(path)
    if path in EXCLUDE_PATCH_PATHS or basename in EXCLUDE_PATCH_PATHS:
        return True
    return any(pattern.fullmatch(basename) for pattern in EXCLUDE_PATCH_BASENAME_PATTERNS)


AGENT_CLS_TO_FAKE_USER_RESPONSE_FN = {
    'CodeActAgent': codeact_user_response,
}


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r'[\s,]+', value.strip())
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        return [
            normalized
            for item in value
            if (normalized := _normalize_optional_string(item)) is not None
        ]
    normalized = _normalize_optional_string(value)
    return [normalized] if normalized else []


def _get_swebench_workspace_dir_name(instance: pd.Series) -> str:
    version = instance.get('version', instance['base_commit'])
    return f'{instance.repo}__{version}'.replace('/', '__')


def _get_task_repo_path(instance: pd.Series) -> str:
    working_dir = instance.get('working_dir')
    if isinstance(working_dir, str):
        working_dir = working_dir.strip()
        if working_dir:
            return working_dir
    elif working_dir is not None and not pd.isna(working_dir):
        working_dir = str(working_dir).strip()
        if working_dir:
            return working_dir

    workspace_dir_name = _get_swebench_workspace_dir_name(instance)
    return f'/workspace/{workspace_dir_name}'


def _quote_task_repo_path(instance: pd.Series) -> str:
    return shlex.quote(_get_task_repo_path(instance))


def get_instruction(instance: pd.Series, metadata: EvalMetadata):
    task_repo_path = _get_task_repo_path(instance)
    # Prepare instruction

    # Instruction based on Anthropic's official trajectory
    # https://github.com/eschluntz/swe-bench-experiments/tree/main/evaluation/verified/20241022_tools_claude-3-5-sonnet-updated/trajs
    instructions = {
        "python":(
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a python code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development Python environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create a script to reproduce the error and execute it with `python <filename.py>` using the BashTool, to confirm the error. When writing a multi-line Python file from Bash, use a heredoc such as `cat > reproduce.py <<\'PY\'` so the file contains real newlines; avoid `echo "...\\n..." > file.py`, which writes literal `\\n` sequences and breaks Python scripts.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "java": (
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a Java code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            "Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n"
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development Java environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f"Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n"
            "Follow these steps to resolve the issue:\n"
            "1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n"
            '2. Create a Java class to reproduce the error and execute it by first compiling with `javac <classname>.java` and then running with `java <classname>` using the BashTool, to confirm the error\n'
            "3. Edit the sourcecode of the repo to resolve the issue.\n"
            "4. Rerun your reproduce script or class and confirm that the error is fixed!\n"
            "5. Think about edgecases, add comprehensive tests for them in your reproduce class or script, and run them to make sure your fix handles these cases as well.\n"
            f"6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance['base_commit']}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n"
            "   - The issue you are fixing\n"
            "   - The files you modified\n"
            "   - The functions or classes you changed\n"
            "   Make sure all these tests pass with your changes.\n"
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "go": (
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a Go code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development Go environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create a script or a function to reproduce the error and execute it with `go run <filename.go>` using the BashTool, to confirm the error.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "c": (
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a C code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development C environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create a script to reproduce the error by compiling your C code (for example, using `gcc <filename.c> -o <executable>`) and then running the executable using the BashTool, to confirm the error.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "cpp": (
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a C++ code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development C++ environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create or adapt a small executable (e.g., a main file or a test driver) to reproduce the issue. Build and run it (for example, by using `g++ -o reproduce reproduce.cpp && ./reproduce` via the BashTool) to confirm the error.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "javascript": (
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a Javascript code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development Javascript environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create a script to reproduce the error and execute it with `node <filename.js>` using the BashTool, to confirm the error.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "typescript":(
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a Typescript code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development Typescript environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create a script to reproduce the error and execute it with `ts-node <filename.ts>` using the BashTool, to confirm the error.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        ),
        "rust":(
            '<uploaded_files>\n'
            f'{task_repo_path}\n'
            '</uploaded_files>\n'
            f"I've uploaded a Rust code repository in the directory {task_repo_path}. OpenHands' own source code lives under /openhands/code, but the repository you need to inspect and modify is at {task_repo_path}. Consider the following issue description:\n\n"
            f'<issue_description>\n'
            f'{instance.get("problem_statement", instance.get("PR_Title", ""))}\n'
            '</issue_description>\n\n'
            'Can you help me implement the necessary changes to the repository so that the requirements specified in the <issue_description> are met?\n'
            "I've already taken care of all changes to any of the test files described in the <issue_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!\n"
            "Also the development Rust environment is already set up for you (i.e., all dependencies already installed), so you don't need to install other packages.\n"
            f'Your task is to make the minimal changes to non-test files in the repository at {task_repo_path} to ensure the <issue_description> is satisfied.\n'
            'Follow these steps to resolve the issue:\n'
            '1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.\n'
            '2. Create a reproduction script (or binary) that triggers the error and execute it with `cargo run --bin <filename>` using the BashTool, to confirm the error.\n'
            '3. Edit the sourcecode of the repo to resolve the issue.\n'
            '4. Rerun your reproduce script and confirm that the error is fixed!\n'
            '5. Think about edgecases, add comprehensive tests for them in your reproduce script, and run them to make sure your fix handles them as well.\n'
            f'6. Once you are done with the initial implementation, please carefully re-read the problem description and check the difference between the current code and the base commit {instance["base_commit"]}. Do you think that the issue has been completely and comprehensively solved? Write tests to check the correctness of the solution, specifically focusing on tests that may point out any remaining problems that are not yet solved. Run all of the tests in the repo and check if any of them fail, and if they do fix the code. Repeat this process of carefully reading the problem description and current implementation, testing, and fixing any problems until you are confident that the current implementation is correct. Find and run any tests in the repo that are related to:\n'
            '   - The issue you are fixing\n'
            '   - The files you modified\n'
            '   - The functions you changed\n'
            '   Make sure all these tests pass with your changes.\n'
            "Your thinking should be thorough and so it's fine if it's very long.\n"
        )
    }
    instruction = instructions.get(LANGUAGE.lower())


    if instruction and RUN_WITH_BROWSING:
        instruction += (
            '<IMPORTANT!>\n'
            'You SHOULD NEVER attempt to browse the web. '
            '</IMPORTANT!>\n'
        )
    return instruction


def clean_git_patch(patch_text: str) -> str:
    """Remove binary/noisy file diffs while preserving unified diff validity."""
    if not patch_text:
        return patch_text

    has_trailing_newline = patch_text.endswith('\n')
    lines = patch_text.splitlines(keepends=True)
    blocks: list[list[str]] = []
    block: list[str] = []
    for line in lines:
        if line.startswith('diff --git '):
            if block:
                blocks.append(block)
            block = [line]
        else:
            block.append(line)
    if block:
        blocks.append(block)

    cleaned_blocks: list[list[str]] = []
    header_re = re.compile(r'^diff --git a/(.+?) b/(.+?)\n?$')
    for b in blocks:
        if not b:
            continue
        block_text = ''.join(b)
        # Keep prior behavior: drop binary file blocks.
        if 'Binary files' in block_text:
            continue

        header = b[0]
        m = header_re.match(header)
        if m:
            a_path, b_path = m.group(1), m.group(2)
            if _should_exclude_patch_path(a_path) or _should_exclude_patch_path(b_path):
                logger.info(f'Excluded generated file from patch: {a_path} -> {b_path}')
                continue

        cleaned_blocks.append(b)

    cleaned = ''.join(''.join(b) for b in cleaned_blocks)
    if has_trailing_newline and cleaned and not cleaned.endswith('\n'):
        cleaned += '\n'
    return cleaned



# TODO: 适应所有的语言
def _get_public_swebench_image(instance_id: str) -> str:
    if '__' not in instance_id:
        raise ValueError(
            f'Cannot derive a public SWE-bench image from instance_id={instance_id!r}'
        )
    repo, name = instance_id.split('__', 1)
    return f'docker.io/swebench/sweb.eval.x86_64.{repo}_1776_{name}:latest'.lower()


def get_instance_docker_image(instance: pd.Series):
    instance_id = _normalize_optional_string(instance.get('instance_id')) or ''

    # 1. Custom Image Mapping (우선순위 1위: 로컬 테스트용)
    custom_image_map_path = _normalize_optional_string(
        os.environ.get('CUSTOM_IMAGE_MAP_PATH')
    )
    if custom_image_map_path and os.path.exists(custom_image_map_path):
        try:
            with open(custom_image_map_path, 'r') as f:
                custom_image_map = json.load(f)
            if instance_id in custom_image_map:
                custom_image = custom_image_map[instance_id]
                logger.info(f'Using custom mapped image for {instance_id}: {custom_image}')
                return custom_image
        except Exception as e:
            logger.warning(f'Failed to load custom image map from {custom_image_map_path}: {e}')

    # 2. JSONL 파일 내 지정 이미지 (우선순위 2위)
    dataset_image = _normalize_optional_string(instance.get('docker_image'))
    if dataset_image:
        return dataset_image

    # 3. Environment override for custom registries
    if DOCKER_IMAGE_PREFIX:
        image_name = ('sweb.eval.x86_64.' + instance_id).replace('__', '_s_')
        return (DOCKER_IMAGE_PREFIX.rstrip('/') + '/' + image_name).lower()

    # 4. Portable public fallback
    if LANGUAGE == 'python':
        fallback_image = _get_public_swebench_image(instance_id)
        logger.info(
            f'No docker_image column value found for {instance_id}; '
            f'falling back to public SWE-bench image {fallback_image}'
        )
        return fallback_image

    raise ValueError(
        'No docker_image was provided for a non-python task. '
        'Set the dataset docker_image column or EVAL_DOCKER_IMAGE_PREFIX.'
    )



def get_config(
    instance: pd.Series,
    metadata: EvalMetadata,
) -> OpenHandsConfig:
    SWE_BENCH_CONTAINER_IMAGE = 'ghcr.io/opendevin/eval-swe-bench:full-v1.2.1'
    if USE_INSTANCE_IMAGE:
        # We use a different instance image for the each instance of swe-bench eval
        # base_container_image = get_instance_docker_image(instance['instance_id'])
        base_container_image = get_instance_docker_image(instance)
        logger.info(
            f'Using instance container image: {base_container_image}. '
            f'Please make sure this image exists. '
            f'Submit an issue on https://github.com/All-Hands-AI/OpenHands if you run into any issues.'
        )
    else:
        base_container_image = SWE_BENCH_CONTAINER_IMAGE
        logger.info(f'Using swe-bench container image: {base_container_image}')

    sandbox_config = get_default_sandbox_config_for_eval()
    sandbox_config.base_container_image = base_container_image
    sandbox_config.enable_auto_lint = True
    sandbox_config.use_host_network = False
    # Add platform to the sandbox config to solve issue 4401
    sandbox_config.platform = 'linux/amd64'
    sandbox_config.remote_runtime_resource_factor = get_instance_resource_factor(
        dataset_name=metadata.dataset,
        instance_id=instance['instance_id'],
    )

    config = get_openhands_config_for_eval(
        metadata=metadata,
        enable_browser=RUN_WITH_BROWSING,
        runtime=os.environ.get('RUNTIME', 'docker'),
        sandbox_config=sandbox_config,
    )
    config.set_llm_config(
        update_llm_config_for_completions_logging(
            metadata.llm_config, metadata.eval_output_dir, instance['instance_id']
        )
    )
    agent_config = AgentConfig(
        enable_jupyter=False,
        enable_browsing=RUN_WITH_BROWSING,
        enable_llm_editor=False,
        condenser=metadata.condenser_config,
        enable_prompt_extensions=False,
    )
    config.set_agent_config(agent_config)
    return config


def initialize_runtime(
    runtime: Runtime,
    instance: pd.Series,  # this argument is not required
):
    """Initialize the runtime for the agent.

    This function is called before the runtime is used to run the agent.
    """
    logger.info('-' * 30)
    logger.info('BEGIN Runtime Initialization Fn')
    logger.info('-' * 30)
    task_repo_path = _get_task_repo_path(instance)
    quoted_task_repo_path = _quote_task_repo_path(instance)
    obs: CmdOutputObservation

    REPO_NAME = instance['repo'].split('/')[-1]
    # Set instance id
    action = CmdRunAction(
        command=f"""echo 'export SWE_INSTANCE_ID={instance['instance_id']}' >> ~/.bashrc && echo 'export PIP_CACHE_DIR=~/.cache/pip' >> ~/.bashrc && echo "alias git='git --no-pager'" >> ~/.bashrc && echo 'export REPO_NAME={REPO_NAME}' >> ~/.bashrc"""
    )
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0, f'Failed to export SWE_INSTANCE_ID: {str(obs)}'
    )
    # pdb.set_trace()
    action = CmdRunAction(command="""export USER=$(whoami); echo USER=${USER} """)
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(obs.exit_code == 0, f'Failed to export USER: {str(obs)}')

    if USE_INSTANCE_IMAGE:
        # inject the init script
        script_dir = os.path.dirname(__file__)

        # inject the instance info
        action = CmdRunAction(command='mkdir -p /swe_util/eval_data/instances')
        action.set_hard_timeout(600)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(
            obs.exit_code == 0,
            f'Failed to create /swe_util/eval_data/instances: {str(obs)}',
        )

        swe_instance_json_name = 'swe-bench-instance.json'
        with tempfile.TemporaryDirectory() as temp_dir:
            # Construct the full path for the desired file name within the temporary directory
            temp_file_path = os.path.join(temp_dir, swe_instance_json_name)
            # Write to the file with the desired name within the temporary directory
            with open(temp_file_path, 'w') as f:
                if not isinstance(instance, dict):
                    json.dump([instance.to_dict()], f, default=str)
                else:
                    json.dump([instance], f, default=str)

            # Copy the file to the desired location
            runtime.copy_to(temp_file_path, '/swe_util/eval_data/instances/')

        # inject the instance swe entry
        runtime.copy_to(
            str(os.path.join(script_dir, 'scripts/setup/instance_swe_entry.sh')),
            '/swe_util/',
        )
        action = CmdRunAction(command='cat ~/.bashrc')
        action.set_hard_timeout(600)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(obs.exit_code == 0, f'Failed to cat ~/.bashrc: {str(obs)}')

        action = CmdRunAction(command='source ~/.bashrc')
        action.set_hard_timeout(600)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        if isinstance(obs, ErrorObservation):
            logger.error(f'Failed to source ~/.bashrc: {str(obs)}')
        assert_and_raise(obs.exit_code == 0, f'Failed to source ~/.bashrc: {str(obs)}')

        action = CmdRunAction(command='source /swe_util/instance_swe_entry.sh')
        action.set_hard_timeout(600)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(
            obs.exit_code == 0,
            f'Failed to source /swe_util/instance_swe_entry.sh: {str(obs)}',
        )
    else:
        action = CmdRunAction(command='source /swe_util/swe_entry.sh')
        action.set_hard_timeout(1800)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(
            obs.exit_code == 0,
            f'Failed to source /swe_util/swe_entry.sh: {str(obs)}',
        )

    action = CmdRunAction(command=f'cd {quoted_task_repo_path}')
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0,
        f'Failed to cd to {task_repo_path}: {str(obs)}',
    )

    action = CmdRunAction(command='git reset --hard')
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(obs.exit_code == 0, f'Failed to git reset --hard: {str(obs)}')

    action = CmdRunAction(
        command='for remote_name in $(git remote); do git remote remove "${remote_name}"; done'
    )
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(obs.exit_code == 0, f'Failed to remove git remotes: {str(obs)}')
    ##TODO:这里看看需不需要判断其他语言的环境
    # action = CmdRunAction(command='which python')
    # action.set_hard_timeout(600)
    # logger.info(action, extra={'msg_type': 'ACTION'})
    # obs = runtime.run_action(action)
    # logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    # assert_and_raise(
    #     obs.exit_code == 0 and 'testbed' in obs.content,
    #     f'Expected to find python interpreter from testbed, but got: {str(obs)}',
    # )

    logger.info('-' * 30)
    logger.info('END Runtime Initialization Fn')
    logger.info('-' * 30)


def complete_runtime(
    runtime: Runtime,
    instance: pd.Series,  # this argument is not required, but it is used to get the task repo path
) -> dict[str, Any]:
    """Complete the runtime for the agent.

    This function is called before the runtime is used to run the agent.
    If you need to do something in the sandbox to get the correctness metric after
    the agent has run, modify this function.
    """
    logger.info('-' * 30)
    logger.info('BEGIN Runtime Completion Fn')
    logger.info('-' * 30)
    obs: CmdOutputObservation
    task_repo_path = _get_task_repo_path(instance)
    quoted_task_repo_path = _quote_task_repo_path(instance)

    action = CmdRunAction(command=f'cd {quoted_task_repo_path}')
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})

    if obs.exit_code == -1:
        # The previous command is still running
        # We need to kill previous command
        logger.info('The previous command is still running, trying to kill it...')
        action = CmdRunAction(command='C-c')
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})

        # Then run the command again
        action = CmdRunAction(command=f'cd {quoted_task_repo_path}')
        action.set_hard_timeout(600)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})

    assert_and_raise(
        isinstance(obs, CmdOutputObservation) and obs.exit_code == 0,
        f'Failed to cd to {task_repo_path}: {str(obs)}',
    )

    action = CmdRunAction(command='git config --global core.pager ""')
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        isinstance(obs, CmdOutputObservation) and obs.exit_code == 0,
        f'Failed to git config --global core.pager "": {str(obs)}',
    )


    action = CmdRunAction(command='git add -A')
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        isinstance(obs, CmdOutputObservation) and obs.exit_code == 0,
        f'Failed to git add -A: {str(obs)}',
    )

    # Unstage known benchmark artifact files so they are never part of model_patch.
    action = CmdRunAction(
        command='''
        for file in $(git status --porcelain | grep -E "^(M| M|\\?\\?|A| A)" | cut -c4-); do
            base=$(basename "$file")
            case "$base" in
                patch.diff|test-output.log|testlog.out|run_test.sh|reproduce*.py|test_script*.py)
                    git restore --staged -- "$file" 2>/dev/null || git reset HEAD -- "$file" >/dev/null 2>&1 || true
                    ;;
            esac
        done
        '''
    )
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})

    # Only unstage true binary diffs. Text scripts can be reported by `file` as
    # "executable", which would incorrectly drop valid source edits.
    action = CmdRunAction(
        command=f'''
        for file in $(git status --porcelain | grep -E "^(M| M|\\?\\?|A| A)" | cut -c4-); do
            if [ -f "$file" ] && git diff --cached --numstat -- "$file" | awk 'NR > 0 && $1 == "-" && $2 == "-" {{found=1}} END {{exit found ? 0 : 1}}'; then
                git restore --staged -- "$file" 2>/dev/null || git reset HEAD -- "$file" >/dev/null 2>&1 || true
                echo "Unstaged binary diff: $file"
            fi
        done
        '''
    )
    action.set_hard_timeout(600)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        isinstance(obs, CmdOutputObservation) and obs.exit_code == 0,
        f'Failed to remove binary files: {str(obs)}',
    )

    # pdb.set_trace()

    n_retries = 0
    git_patch = None
    while n_retries < 5:
        action = CmdRunAction(
            command=f'git diff --no-color --cached {instance["base_commit"]} > patch.diff'
        )
        action.set_hard_timeout(max(300 + 100 * n_retries, 600))
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        n_retries += 1
        if isinstance(obs, CmdOutputObservation):
            if obs.exit_code == 0:
                # git_patch = obs.content.strip()
                break
            else:
                logger.info('Failed to get git diff, retrying...')
                sleep_if_should_continue(10)
        elif isinstance(obs, ErrorObservation):
            logger.error(f'Error occurred: {obs.content}. Retrying...')
            sleep_if_should_continue(10)
        else:
            assert_and_raise(False, f'Unexpected observation type: {str(obs)}')

    action = FileReadAction(
            path='patch.diff'
        )
    action.set_hard_timeout(max(300 + 100 * n_retries, 600))
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    git_patch = obs.content
    # pdb.set_trace()

    assert_and_raise(git_patch is not None, 'Failed to get git diff (None)')

    logger.info('-' * 30)
    logger.info('END Runtime Completion Fn')
    logger.info('-' * 30)
    return {'git_patch': git_patch}


def process_instance(
    instance: pd.Series,
    metadata: EvalMetadata,
    reset_logger: bool = True,
    runtime_failure_count: int = 0,
) -> EvalOutput:
    config = get_config(instance, metadata)

    # Setup the logger properly, so you can run multi-processing to parallelize the evaluation
    if reset_logger:
        log_dir = os.path.join(metadata.eval_output_dir, 'infer_logs')
        reset_logger_for_multiprocessing(logger, instance.instance_id, log_dir)
    else:
        logger.info(f'Starting evaluation for instance {instance.instance_id}.')

    # Increase resource_factor with increasing attempt_id
    if runtime_failure_count > 0:
        config.sandbox.remote_runtime_resource_factor = min(
            config.sandbox.remote_runtime_resource_factor * (2**runtime_failure_count),
            8,
        )
        logger.warning(
            f'This is the {runtime_failure_count + 1}th attempt for instance {instance.instance_id}, setting resource factor to {config.sandbox.remote_runtime_resource_factor}'
        )
    # pdb.set_trace()
    runtime = create_runtime(config)
    call_async_from_sync(runtime.connect)

    try:
        initialize_runtime(runtime, instance)

        instruction = get_instruction(instance, metadata)

        # Here's how you can run the agent (similar to the `main` function) and get the final task state
        state: State | None = asyncio.run(
            run_controller(
                config=config,
                initial_user_action=MessageAction(content=instruction),
                runtime=runtime,
                fake_user_response_fn=AGENT_CLS_TO_FAKE_USER_RESPONSE_FN[
                    metadata.agent_class
                ],
            )
        )

        # if fatal error, throw EvalError to trigger re-run
        if is_fatal_evaluation_error(state.last_error):
            raise EvalException('Fatal error detected: ' + state.last_error)

        # ======= THIS IS SWE-Bench specific =======
        # Get git patch
        return_val = complete_runtime(runtime, instance)
        git_patch = return_val['git_patch']
        logger.info(
            f'Got git diff for instance {instance.instance_id}:\n--------\n{git_patch}\n--------'
        )
    finally:
        runtime.close()
    # ==========================================

    # ======= Attempt to evaluate the agent's edits =======
    # we use eval_infer.sh to evaluate the agent's edits, not here
    # because the agent may alter the environment / testcases
    git_patch = clean_git_patch(git_patch)
    test_result = {
        'git_patch': git_patch,
    }

    # If you are working on some simpler benchmark that only evaluates the final model output (e.g., in a MessageAction)
    # You can simply get the LAST `MessageAction` from the returned `state.history` and parse it for evaluation.
    if state is None:
        raise ValueError('State should not be None.')

    # NOTE: this is NO LONGER the event stream, but an agent history that includes delegate agent's events
    histories = [event_to_dict(event) for event in state.history]
    metrics = get_metrics(state)

    # Save the output
    output = EvalOutput(
        instance_id=instance.instance_id,
        instruction=instruction,
        instance=instance.to_dict(),  # SWE Bench specific
        test_result=test_result,
        metadata=metadata,
        history=histories,
        metrics=metrics,
        error=state.last_error if state and state.last_error else None,
    )
    return output


def filter_dataset(dataset: pd.DataFrame, filter_column: str) -> pd.DataFrame:
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.toml')
    instance_ids = _parse_id_list(os.environ.get('INSTANCE_IDS'))
    if instance_ids:
        logger.info(f'Filtering {len(instance_ids)} tasks from "INSTANCE_IDS"...')
        dataset = dataset[dataset[filter_column].isin(instance_ids)]
        logger.info(f'Retained {dataset.shape[0]} tasks after INSTANCE_IDS filtering')
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = toml.load(file)
            selected_ids = _parse_id_list(data.get('selected_ids'))
            if selected_ids and not instance_ids:
                logger.info(
                    f'Filtering {len(selected_ids)} tasks from "selected_ids"...'
                )
                dataset = dataset[dataset[filter_column].isin(selected_ids)]
                logger.info(f'Retained {dataset.shape[0]} tasks after filtering')
    skip_ids = _parse_id_list(os.environ.get('SKIP_IDS'))
    if skip_ids:
        logger.info(f'Filtering {len(skip_ids)} tasks from "SKIP_IDS"...')
        dataset = dataset[~dataset[filter_column].isin(skip_ids)]
    return dataset


if __name__ == '__main__':
    # pdb.set_trace()
    parser = get_evaluation_parser()
    parser.add_argument(
        '--dataset',
        type=str,
        default='princeton-nlp/SWE-bench',
        help='data set to evaluate on, either full-test or lite-test',
    )
    parser.add_argument(
        '--split',
        type=str,
        default='test',
        help='split to evaluate on',
    )
    args, _ = parser.parse_known_args()

    # NOTE: It is preferable to load datasets from huggingface datasets and perform post-processing
    # so we don't need to manage file uploading to OpenHands's repo
    if args.dataset.endswith('.xlsx'):
        from datasets import Dataset, DatasetDict
        df = pd.read_excel(args.dataset, engine='openpyxl')
        dataset = DatasetDict({args.split: Dataset.from_pandas(df)})
    elif args.dataset.endswith('.jsonl') or args.dataset.endswith('.json'):
        dataset = load_dataset('json', data_files={args.split: args.dataset})
    else:
        dataset = load_dataset(args.dataset)
    dataset = dataset[args.split]
    swe_bench_tests = filter_dataset(dataset.to_pandas(), 'instance_id')
    logger.info(
        f'Loaded dataset {args.dataset} with split {args.split}: {len(swe_bench_tests)} tasks'
    )

    llm_config = None
    if args.llm_config:
        llm_config = get_llm_config_arg(args.llm_config, toml_file=args.config_file)
        llm_config.log_completions = True
        # modify_params must be False for evaluation purpose, for reproducibility and accurancy of results
        llm_config.modify_params = False

    if llm_config is None:
        raise ValueError(f'Could not find LLM config: --llm_config {args.llm_config}')

    details = {}
    _agent_cls = openhands.agenthub.Agent.get_cls(args.agent_cls)

    dataset_descrption = (
        args.dataset.replace('/', '__') + '-' + args.split.replace('/', '__')
    )
    metadata = make_metadata(
        llm_config,
        dataset_descrption,
        args.agent_cls,
        args.max_iterations,
        args.eval_note,
        args.eval_output_dir,
        details=details,
    )

    output_file = os.path.join(metadata.eval_output_dir, 'output.jsonl')
    print(f'### OUTPUT FILE: {output_file} ###')
    instances = prepare_dataset(swe_bench_tests, output_file, args.eval_n_limit)

    if len(instances) > 0 and not isinstance(
        instances['FAIL_TO_PASS'][instances['FAIL_TO_PASS'].index[0]], str
    ):
        for col in ['PASS_TO_PASS', 'FAIL_TO_PASS']:
            instances[col] = instances[col].apply(lambda x: str(x))
    # if LANGUAGE == "java": ##TODO:适配多语言的版本
    #     for col in ['issue_numbers', 'created_at']:
    #         instances[col] = instances[col].apply(lambda x: str(x))
    run_evaluation(
        instances,
        metadata,
        output_file,
        args.eval_num_workers,
        process_instance,
        timeout_seconds=120 * 60,  # 2 hour PER instance should be more than enough
        max_retries=5,
    )
