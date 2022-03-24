import logging
from functools import wraps
from typing import Callable, List, Optional, Type

import click
from pydantic import parse_obj_as
from yaml import safe_load

from mlem import version
from mlem.analytics import send_cli_call
from mlem.constants import MLEM_DIR
from mlem.core.base import MlemObject, build_mlem_object
from mlem.core.errors import WrongMetaType
from mlem.core.metadata import load_meta
from mlem.core.objects import MlemMeta


@click.group()
@click.version_option(version.__version__)
def cli():
    """\b
    MLEM is a tool to help you version and deploy your Machine Learning models:
    * Serialize any model trained in Python into ready-to-deploy format
    * Model lifecycle management using Git and GitOps principles
    * Provider-agnostic deployment
    """


def _set_log_level(ctx, param, value):  # pylint: disable=unused-argument
    if value:
        logger = logging.getLogger("mlem")
        logger.handlers[0].setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)


verbose_option = click.option(
    "-v",
    "--verbose",
    callback=_set_log_level,
    expose_value=False,
    is_eager=True,
    is_flag=True,
)


def _send_analytics(cmd_name):
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            res = {}
            error = None
            try:
                res = f(*args, **kwargs) or {}
                res = {f"cmd_{cmd_name}_{k}": v for k, v in res.items()}
            except Exception as e:
                error = str(type(e))
                raise e
            finally:
                send_cli_call(cmd_name, error_msg=error, **res)

        return inner

    return decorator


@wraps(cli.command)
def mlem_command(*args, **kwargs):
    def decorator(f):
        if len(args) > 0:
            cmd_name = args[0]
        else:
            cmd_name = kwargs.get("name", f.__name__)
        return cli.command(*args, **kwargs)(
            _send_analytics(cmd_name)(verbose_option(f))
        )

    return decorator


option_repo = click.option(
    "-r", "--repo", default=None, help="Path to MLEM repo"
)
option_rev = click.option("--rev", default=None, help="Repo revision to use.")
option_link = click.option(
    "--link/--no-link",
    default=False,
    help="Whether to create link for output in .mlem directory.",
)
option_external = click.option(
    "--external",
    "-e",
    default=False,
    is_flag=True,
    help=f"Save object not in {MLEM_DIR}, but directly in repo.",
)
option_target_repo = click.option(
    "--target-repo",
    "--tr",
    default=None,
    help="Save object to mlem dir found in {target_repo} path.",
)


def config_arg(name: str, model: Type[MlemObject], **kwargs):
    """add argument + multi option -c and -f to configure and deserialize to model"""

    def decorator(f):
        @click.option("-l", "--load", default=None)
        @click.argument("subtype", default="", **kwargs)
        @click.option("-c", "--conf", multiple=True)
        @click.option("-f", "--file_conf", multiple=True)
        @wraps(f)
        def inner(
            load: Optional[str],
            subtype: str,
            conf: List[str],
            file_conf: List[str],
            **inner_kwargs,
        ):
            if load is not None:
                with open(load, "r", encoding="utf8") as of:
                    obj = parse_obj_as(model, safe_load(of))
            else:
                obj = build_mlem_object(model, subtype, conf, file_conf)
            inner_kwargs[name] = obj
            return f(**inner_kwargs)

        return inner

    return decorator


def _get_option_name(option: Callable):
    option_decls = option.__closure__[-1].cell_contents  # type: ignore
    return option_decls[-1].lstrip("-")


def with_meta(
    argument_name: str,
    repo_opt: Callable = option_repo,
    rev_opt: Callable = option_rev,
    force_cls: Type[MlemMeta] = None,
):
    def decorator(f):
        @click.argument(argument_name)
        @repo_opt
        @rev_opt
        @wraps(f)
        def inner(**kwargs):
            path = kwargs.pop(argument_name)
            repo = kwargs.pop(_get_option_name(repo_opt))
            rev = kwargs.pop(_get_option_name(rev_opt))
            meta = load_meta(path, repo=repo, rev=rev)
            if force_cls is not None and not isinstance(meta, force_cls):
                raise WrongMetaType(meta, force_cls)
            kwargs[argument_name] = meta
            return f(**kwargs)

        return inner

    return decorator
