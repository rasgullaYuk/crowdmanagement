# CSRNet model weights (`weights.pth`)

The backend now supports **degraded mode** when model weights are missing.

## Where to place the weights file

Put `weights.pth` at:

`C:\Users\inchara P\crowdmanagement\Public_Safety\weights.pth`

This is the project root (one level above `backend/`).

## What happens if the file is missing

- backend startup does **not** crash
- a clear warning is logged
- crowd-stream model features run in degraded mode until weights are added
