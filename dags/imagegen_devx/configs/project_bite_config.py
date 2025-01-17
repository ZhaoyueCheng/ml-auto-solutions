# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities to construct configs for solutionsteam_jax_bite DAG."""


import datetime
from typing import Tuple
from xlml.apis import gcp_config, metric_config, task, test_config
from dags import gcs_bucket, test_owner
from dags.imagegen_devx.configs import common
from dags.vm_resource import TpuVersion, Project
from airflow.models.taskmixin import DAGNode


GCS_SUBFOLDER_PREFIX = test_owner.Team.IMAGEGEN_DEVX.value


def set_up_axlearn() -> Tuple[str]:
  return (
      common.UPGRADE_PIP,
      "git clone https://github.com/apple/axlearn.git",
      "python -m pip install ./axlearn",
      *common.set_up_nightly_jax(),
  )


def get_bite_tpu_config(
    tpu_version: TpuVersion,
    tpu_cores: int,
    tpu_zone: str,
    runtime_version: str,
    model_config: str,
    time_out_in_min: int,
    is_tpu_reserved: bool = False,
):
  job_gcp_config = gcp_config.GCPConfig(
      project_name=Project.CLOUD_ML_AUTO_SOLUTIONS.value,
      zone=tpu_zone,
      dataset_name=metric_config.DatasetOption.XLML_DATASET,
  )

  set_up_cmds = set_up_axlearn()
  run_model_cmds = (
      (
          "cd axlearn && python -m axlearn.common.launch_trainer_main"
          f" --module=text.gpt.c4_trainer --config={model_config}"
          f" --trainer_dir={metric_config.SshEnvVars.GCS_OUTPUT.value}"
          f" --data_dir={gcs_bucket.AXLEARN_DIR} --jax_backend=tpu"
      ),
  )

  job_test_config = test_config.TpuVmTest(
      test_config.Tpu(
          version=tpu_version,
          cores=tpu_cores,
          runtime_version=runtime_version,
          reserved=is_tpu_reserved,
      ),
      test_name=f"jax_{model_config}",
      set_up_cmds=set_up_cmds,
      run_model_cmds=run_model_cmds,
      timeout=datetime.timedelta(minutes=time_out_in_min),
      task_owner=test_owner.RAN_R,
      gcs_subfolder=f"{GCS_SUBFOLDER_PREFIX}/jax",
  )

  return task.run_queued_resource_test(
      task_test_config=job_test_config,
      task_gcp_config=job_gcp_config,
  )
