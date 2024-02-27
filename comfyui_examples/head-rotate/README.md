# How to make head-rotate workflow in ComfyUI

## Prerequisite

* Load the **head-rotate-character-animatediff-sheet.png** into ComfyUI via drag and drop or over the ComfyUI-Manager Load button, you will see the workflow: 


![](./head-rotate-character-animatediff-sheet.png)


* Make sure the version is updated via Manager ‘**update all**’ button
* Install the **missing custom nodes** from Manager Plugin 
* Assets list:
    * Custom nodes:
        * Manager: https://github.com/ltdrdata/ComfyUI-Manager
        * Image pixelization: https://github.com/WASasquatch/was-node-suite-comfyui
        * JobIterator: https://github.com/ali1234/comfyui-job-iterator
        * AnimateDiff: https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved
    * ControlNets:
        * openpose + lineart: https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors
    * Lora:
        * lcm-lora-sd1.5: https://huggingface.co/latent-consistency/lcm-lora-sdv1-5
        * pixel-sprite: https://civitai.com/models/165876/2d-pixel-toolkit-2d 
    * Checkpoints:
        * all-in-one-pixel-model: https://civitai.com/models/34/all-in-one-pixel-model 

## Generate

* Load **head-rotate-character-sheet.jpg** to extract head openpose information and lineart. 
* The **all-in-one-pixel-model** is the base model. **Pixel-sprite** lora enhances the pixel art style. 
* **Lcm-lora-sd1.5** lora accelerates the overall speed with only 4-5 sampling steps and cfg ~= .15.
* **Pixelization** fixes any broken or misaligned pixels. 
* The end-to-end time is about **3-5s** (2 controlnets, 2 loras, 1 perfect pixel).
* Crop the output image to 15-frames for each head angle
* Send it to img2gif(https://imgflip.com/gif-maker) website


