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

"""A DAG to run end-to-end MaxText tests."""


import datetime
from airflow import models
from dags import composer_env
from dags.vm_resource import TpuVersion, Zone, MachineVersion, ImageProject, ImageFamily, GpuVersion
from dags.multipod.configs import maxtext_gce_config
from dags.multipod.configs.common import SetupMode, Platform


# Run once a day at 4 am UTC (8 pm PST)
SCHEDULED_TIME = "0 4 * * *" if composer_env.is_prod_env() else None


with models.DAG(
    dag_id="maxtext_end_to_end",
    schedule=SCHEDULED_TIME,
    tags=["multipod_team", "maxtext", "stable", "nightly"],
    start_date=datetime.datetime(2024, 1, 19),
    catchup=False,
) as dag:
  test_name_prefix = "maxtext"
  test_models = {
      "llama2": ["test_llama2", "llama_finetuning_test"],
      "mistral": ["test_mistral"],
      "gamma": ["test_gamma"],
      "gpt3": ["test_gpt3"],
  }
  test_modes = [SetupMode.STABLE, SetupMode.NIGHTLY]
  maxtext_end2end_tpu = [DummyOperator(task_id="maxtext_end2end_tpu")]
  maxtext_end2end_gpu = [DummyOperator(task_id="maxtext_end2end_gpu")]
  for model in test_models.keys():
    for mode in test_modes:
      for test_script in test_models[model]:
        test_tpu = maxtext_gce_config.get_maxtext_end_to_end_test_config(
            tpu_version=TpuVersion.V4,
            tpu_cores=8,
            tpu_zone=Zone.US_CENTRAL2_B.value,
            time_out_in_min=60,
            is_tpu_reserved=False,
            test_name=f"{test_name_prefix}-{mode.value}-{test_script}",
            test_script=test_script,
            test_mode=mode,
        ).run()
        maxtext_end2end_tpu[-1] >> test_tpu
        maxtext_end2end_tpu.append(test_tpu)

        test_gpu = maxtext_gce_config.get_maxtext_end_to_end_gpu_test_config(
            machine_type=MachineVersion.A3_HIGHGPU_8G,
            image_project=ImageProject.DEEP_LEARNING_PLATFORM_RELEASE,
            image_family=ImageFamily.COMMON_CU121_DEBIAN_11,
            accelerator_type=GpuVersion.H100,
            gpu_cores=8,
            gpu_zone=Zone.US_CENTRAL1_A.value,
            time_out_in_min=60,
            test_name=f"{test_name_prefix}-{mode.value}-{test_script}",
            test_script=test_script,
            test_mode=mode,
        ).run()
        maxtext_end2end_gpu[-1] >> test_gpu
        maxtext_end2end_gpu.append(test_gpu)
