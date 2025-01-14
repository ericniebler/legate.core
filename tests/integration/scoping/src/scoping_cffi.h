/* Copyright 2023 NVIDIA Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

#ifndef __REGISTER_C__
#define __REGISTER_C__

#ifdef __cplusplus
extern "C" {
#endif

enum RegistryOpCode {
  MULTI_VARIANT    = 0,
  CPU_VARIANT_ONLY = 1,
};

void perform_registration(void);

#ifdef __cplusplus
}
#endif

#endif  // __REGISTER_C__
