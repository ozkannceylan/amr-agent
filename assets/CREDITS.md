# assets — provenance

Every image in this directory was produced from this repository or from
permissively licensed sources. No vendor marketing material is used.

| File | Origin |
|---|---|
| `plc-drives-cell.gif` | Screen capture of `sim/worlds/cell.sdf` in Gazebo Harmonic, driven live by the S7-1500 standard program on PLCSIM Advanced. |
| `demo-cell.png` | Screen capture of `sim/worlds/cell.sdf` in Gazebo Harmonic. |
| `rb-kairos-gazebo.png` | Own render of the manufacturer's ROS 2 description of the Robotnik RB-Kairos, in Gazebo Harmonic 8.11.0 under a headless llvmpipe renderer. See below. |

## rb-kairos-gazebo.png

The model was expanded with `xacro` from `robots/rbkairos/rbkairos.urdf.xacro`
and rendered unmodified. Sources, at the commits used:

| Package | Repository | Branch | Commit |
|---|---|---|---|
| `robotnik_description` | https://github.com/RobotnikAutomation/robotnik_description | `jazzy-devel` | `4bc73425d090ead4591a7091e7ef7e7dc4fe862a` |
| `robotnik_sensors` | https://github.com/RobotnikAutomation/robotnik_sensors | `jazzy-devel` | `fe923150cddca935edc13a645566cbb2aa7417dd` |

Both packages are BSD-3-Clause. Neither is vendored into this repository; they
were fetched outside the working tree for the render only. The mesh and
material assets visible in the image are the vendor's, and their licence
notice is reproduced here as that licence requires:

```
Copyright (c) 2025, Robotnik Automation S.L.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its contributors
  may be used to endorse or promote products derived from this software without
  specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

The RB-Kairos render carries no claim about this project's own progress: the
vehicle enters the demonstration at M5, and nothing in it has been integrated
yet.
