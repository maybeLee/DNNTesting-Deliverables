## API 
import os
import shutil
import subprocess
from util import check_docker_exists


class DNNTest(object):
    def __init__(self, container_name="DNNTesting"):
        self.container_name = container_name
        self.crunner = "docker" if check_docker_exists() else "podman"

    def numerical_analysis(self, model_name):
        if not model_name.endswith(".pbtxt"):
            raise ValueError(f"Invalid model: {model_name}. The model format should be pbtxt")
        cmd = f"{self.crunner} exec {self.container_name} /bin/sh -c 'cd DEBAR && CONDA_PREFIX=/opt/conda/envs/debar PATH=/opt/conda/envs/debar/bin:$PATH /opt/conda/envs/debar/bin/python analysis_main.py ./computation_graphs_and_TP_list/computation_graphs/{model_name}'"
        result = subprocess.check_output(cmd, shell=True)
        return result

    def detect_yolov7(self, img_path, weights_path, size=320, confidence=0.25):
        assert img_path.endswith(".jpg")
        model_name: str = weights_path.split("runs/train/")[-1].split("/")[0]
        output_dir = f"/root/MetaHand/tools/yolov7/runs/detect/{model_name}"
        cmd = f"{self.crunner} exec {self.container_name}  /bin/sh -c 'cd MetaHand && CONDA_PREFIX=/opt/conda/envs/metahand PATH=/opt/conda/envs/metahand/bin:$PATH /opt/conda/envs/metahand/bin/python -m scripts.evaluation.detect_parallel_yolov7 " \
              f"--img_dir {img_path} " \
              f"--weights_path {weights_path} " \
              f"--save_dir={output_dir} " \
              f"--size {size} " \
              f"--confidence {confidence} " \
              f"--jobs=8'"
        subprocess.call(cmd, shell=True)
        img_name = os.path.basename(img_path)
        res_path = f"./MetaHand/tools/yolov7/runs/detect/{model_name}/{img_name}/{img_name}"
        return res_path

    def detect_yolov7_dir(self, img_path="/root/MetaHand/tools/yolov7/pilotstudy/images/train",
                          weights_path="/root/MetaHand/tools/yolov7/runs/train/pilotstudy_640/weights/best.pt",
                          size=640, confidence=0.25):
        model_name: str = weights_path.split("runs/train/")[-1].split("/")[0]
        output_dir = f"/root/MetaHand/tools/yolov7/runs/detect/{model_name}"
        cmd = f"{self.crunner} exec {self.container_name}  /bin/sh -c 'cd MetaHand && CONDA_PREFIX=/opt/conda/envs/metahand PATH=/opt/conda/envs/metahand/bin:$PATH /opt/conda/envs/metahand/bin/python -m scripts.evaluation.detect_parallel_yolov7 " \
              f"--img_dir {img_path} " \
              f"--weights_path {weights_path} " \
              f"--save_dir={output_dir} " \
              f"--size {size} " \
              f"--confidence {confidence} " \
              f"--jobs=8'"
        subprocess.call(cmd, shell=True)
        img_name = os.path.basename(img_path)
        res_path = f"./MetaHand/tools/yolov7/runs/detect/{model_name}/{img_name}/{img_name}"
        return res_path

    def prepare_dataset(self, dataset_name="", image_path="", label_path="", train_val_ratio=0.8):
        if not image_path.startswith("/root"):
            image_path = os.path.join("/root", image_path)
        if not label_path.startswith("/root"):
            label_path = os.path.join("/root", label_path)
        cmd = f"{self.crunner} exec {self.container_name}  /bin/sh -c 'cd MetaHand && CONDA_PREFIX=/opt/conda/envs/metahand PATH=/opt/conda/envs/metahand/bin:$PATH /opt/conda/envs/metahand/bin/python -m scripts.dataset.yolov7_dataset_preparation " \
              f"--src_img_dir {image_path} " \
              f"--src_label_dir {label_path} " \
              f"--target_dir ./tools/yolov7/{dataset_name}'"
        subprocess.call(cmd, shell=True)
        res_path = f"./MetaHand/tools/yolov7/{dataset_name}"
        shutil.copy(os.path.join(res_path, "data.yaml"), f"./MetaHand/tools/yolov7/data/{dataset_name}.yaml")
        return res_path

    def train_yolov7(self, proj_name="pilotstudy", data_path="/root/MetaHand/tools/yolov7/pilotstudy/data.yaml",
                     img_size=640, batch_size=42, num_workers=4, num_epoch=300, cfg_path="cfg/training/yolov7.yaml"):
        # The path can be an absolute path or relative path with the root to be ./MetaHand/tools/yolov7
        if not os.path.exists(data_path):
            if not os.path.exists(data_path.replace("/root", os.getcwd())):
                raise ValueError(f"The data path: {data_path} does not exist!")
        import torch
        if torch.cuda.is_available():
            cmd = f'{self.crunner} exec {self.container_name}  /bin/sh -c \'cd MetaHand/tools/yolov7 && /opt/conda/envs/metahand/bin/python -m torch.distributed.launch ' \
                  f'--nproc_per_node 3 --master_port 9527 train.py --workers {num_workers} --device 1,0,2 ' \
                  f'--sync-bn --batch-size {batch_size} --data {data_path} ' \
                  f'--img {img_size} --cfg {cfg_path} --weights "" ' \
                  f'--name {proj_name} --epochs {num_epoch} --hyp data/hyp.scratch.p5.yaml\''
        else:
            cmd = f'{self.crunner} exec {self.container_name}  /bin/sh -c \'cd MetaHand/tools/yolov7 && /opt/conda/envs/metahand/bin/python ' \
                  f'train.py --workers 1 --device cpu ' \
                  f'--batch-size 2 --data {data_path} ' \
                  f'--img 320 --cfg {cfg_path} --weights "" ' \
                  f'--name {proj_name} --epochs {num_epoch} --hyp data/hyp.scratch.p5.cpu.yaml\''
        subprocess.call(cmd, shell=True)

    def evaluate_yolov7(
            self, data_dir="/root/MetaHand/tools/yolov7/pilotstudy",
            weights_path="/root/MetaHand/tools/yolov7/runs/train/pilotstudy_640/weights/best.pt",
            mutate_type="ObjectGaussianMutation",
            mutate_ratio="03",
            mutate_strength=160,
            threshold=0.3,
            image_size=640,
            jobs=8
    ):
        print(f"The weight path is: {weights_path}")
        model_name: str = weights_path.split("runs/train/")[-1].split("/")[0]
        log_dir = f"/root/MetaHand/logs/yolov7/{mutate_type}"
        output_dir = f"/root/MetaHand/tools/yolov7/runs/detect/{model_name}"
        mutate_name = f"object_gaussian_{mutate_strength}_fixMutRatio_centerXY_{mutate_ratio}"
        mutate_image = f"{data_dir}/{mutate_type}/{mutate_name}"
        origin_image = f"{data_dir}/images/train"
        origin_label = f"{data_dir}/labels/train"
        MR = 2
        os.makedirs(log_dir.replace("/root/", ""), exist_ok=True)
        os.makedirs(output_dir.replace("/root/", ""), exist_ok=True)
        cmd = f"{self.crunner} exec {self.container_name} /bin/sh -c " \
              f"'" \
              f"cd MetaHand && CONDA_PREFIX=/opt/conda/envs/metahand PATH=/opt/conda/envs/metahand/bin:$PATH " \
              f"/opt/conda/envs/metahand/bin/python -u -m scripts.evaluation.evaluate " \
              f"-oi={origin_image} " \
              f"-mi={mutate_image} " \
              f"-ol={origin_label} " \
              f"-olf=yolov7 " \
              f"-w={weights_path} " \
              f"-od={output_dir} " \
              f"--dataset=yolov7 " \
              f"--mr={MR} " \
              f"-img_size={image_size} " \
              f"--jobs={jobs} " \
              f"--threshold={threshold}" \
              f"'"
        subprocess.call(cmd, shell=True)
        violation_path = f"/root/MetaHand/{mutate_name}_violations.txt"
        return violation_path

    def repair_yolov7(
            self,
            data_dir="/root/MetaHand/tools/yolov7/pilotstudy",
            weights_path="/root/MetaHand/tools/yolov7/runs/train/pilotstudy_640/weights/best.pt",
            mutate_type="ObjectGaussianMutation",
            mutate_ratio="03",
            mutate_strength=160,
            threshold=0.3,
            img_size=640,
            num_epoch=300
    ):
        violation_path = self.evaluate_yolov7(data_dir=data_dir, weights_path=weights_path, mutate_type=mutate_type,
                                              mutate_strength=mutate_strength, mutate_ratio=mutate_ratio)
        mutate_name = f"object_gaussian_{mutate_strength}_fixMutRatio_centerXY_{mutate_ratio}"
        data_name = data_dir.rstrip("/").split("/")[-1]
        base_dir = f"/root/MetaHand/tools/yolov7/runs/train/{data_name}/{mutate_type}/{mutate_name}_{threshold}"
        v7_base = f"./runs/train/{data_name}/{mutate_type}/{mutate_name}_{threshold}"
        os.makedirs(base_dir.replace("/root/", ""), exist_ok=True)
        shutil.move(violation_path.replace("/root/", ""),
                    os.path.join(base_dir.replace("/root/", ""), f"{mutate_name}_violations.txt"))

        # new train file will be saved in ./{base_dir}/train.txt
        cmd = f"{self.crunner} exec {self.container_name} /bin/sh -c " \
              f"'" \
              f"cd MetaHand && CONDA_PREFIX=/opt/conda/envs/metahand PATH=/opt/conda/envs/metahand/bin:$PATH " \
              f"/opt/conda/envs/metahand/bin/python -u -m scripts.train.prepare_train_data " \
              f"--source_path={base_dir}/{mutate_name}_violations.txt " \
              f"--origin_source_path={data_dir}/train.txt " \
              f"--target_dir={base_dir} " \
              f"--dataset=yolov7 " \
              f"'"
        subprocess.call(cmd, shell=True)
        train_txt = f"{v7_base}/train.txt"
        subprocess.call(f"rm ./MetaHand/tools/yolov7/{train_txt.replace('.txt', '.cache')}", shell=True)
        src_yaml = os.path.join(data_dir, "data.yaml")
        dst_yaml = os.path.join(base_dir, "data.yaml")
        shutil.copy(src_yaml.replace("/root/", ""), dst_yaml.replace("/root/", ""))
        with open(dst_yaml.replace("/root/", ""), "r") as file:
            content = file.read().rstrip().splitlines()
        new_yaml = ""
        for line in content:
            if line.startswith("train:"):
                new_yaml += f"train: {train_txt}\n"
            else:
                new_yaml += line + "\n"
        with open(dst_yaml.replace("/root/", ""), "w") as file:
            file.write(new_yaml)
        self.train_yolov7(proj_name=f"{data_name}_yolov7_{mutate_name}_{img_size}", data_path=dst_yaml, img_size=img_size, num_epoch=num_epoch)

    def mutate_image(self, file_or_directory: str, image_path: str, label_path: str,
                     output_path: str = "./MetaHand/data_pilot_test/test_mutate", mutate_type: str = "object", mutate_ratio: str = "0.9",
                     noise_intensity: str = "16.0", label_format: str = "darknet") -> str:
        """
        Generate mutated images on target {img_path}.
        If the {img_path} is a directory, this function will mutate all images inside the directory.
        If the {img_path} is a file, this function will mutate the target image.
        :param file_or_directory: "file" or "directory"
        :param image_path
        :param label_path
        :param output_path: directory that stores mutated images
        :param mutate_type: "background" or "object"
        :param mutate_ratio: 0.0-1.0
        :param noise_intensity: 0.0-1.0
        :param label_format: "darknet" or "coco"
        :return: the directory of mutated images
        """
        # python -O ./scripts/mutation/mutation_operation.py --image_path $1 --label_path $2 --mutate_path $3 --random_erase $5 --random_erase_mode fixMutRatio_centerXY --guassian_sigma $6 --object_or_background $4 --dataset $7
        # python -O ./scripts/mutation/mutation_operation.py --image_path /ssddata1/users/dlproj/MetaHand/data_pilot/images/0a0c5746-frame946.jpg --label_path /ssddata1/users/dlproj/MetaHand/data_pilot/labels/0a0c5746-frame946.txt --mutate_path $3 --random_erase $5 --random_erase_mode fixMutRatio_centerXY --guassian_sigma $6 --object_or_background $4 --dataset $7
        # assert os.path.exists(image_path)
        # assert os.path.exists(label_path)
        if file_or_directory == "file":
            cmd = f"{self.crunner}  exec {self.container_name} /bin/bash -c \"source ~/.bashrc; conda activate metahand; \
            python -O /root/MetaHand/scripts/mutation/mutation_operation_single.py --image_path {image_path} \
            --label_path {label_path} --mutate_path {output_path} --random_erase {mutate_ratio} \
            --random_erase_mode fixMutRatio_centerXY --guassian_sigma {noise_intensity} \
            --object_or_background {mutate_type} --dataset {label_format}\""
            # Example: podman exec DNNTesting /bin/bash -c "source ~/.bashrc; conda activate metahand; python -O /root/MetaHand/scripts/mutation/mutation_operation_single.py --image_path /root/MetaHand/data_pilot_test/images/000fbcd9-frame144.jpg --label_path /root/MetaHand/data_pilot_test/labels/000fbcd9-frame144.txt --mutate_path /root/MetaHand/data_pilot_test/test_mutate --random_erase 0.9 --random_erase_mode fixMutRatio_centerXY --guassian_sigma 16.0 --object_or_background object --dataset darknet"
        elif file_or_directory == "directory":
            cmd = f"{self.crunner} exec {self.container_name} /bin/bash -c \"source ~/.bashrc; conda activate metahand; \
            python -O /root/MetaHand/scripts/mutation/mutation_operation.py --image_path {image_path} \
            --label_path {label_path} --mutate_path {output_path} --random_erase {mutate_ratio} \
            --random_erase_mode fixMutRatio_centerXY --guassian_sigma {noise_intensity} \
            --object_or_background {mutate_type} --dataset {label_format}\""
            # Example: podman exec DNNTesting /bin/bash -c "source ~/.bashrc; conda activate metahand; python -O /root/MetaHand/scripts/mutation/mutation_operation.py --image_path /root/MetaHand/data_pilot_test/images/ --label_path /root/MetaHand/data_pilot_test/labels/ --mutate_path /root/MetaHand/data_pilot_test/test_mutate --random_erase 0.9 --random_erase_mode fixMutRatio_centerXY --guassian_sigma 16.0 --object_or_background object --dataset darknet"
        else:
            raise ValueError("please specify file or directory")
        subprocess.call(cmd, shell=True)
        if mutate_type == "object":
            output_path = os.path.join(output_path, f"ObjectGaussianMutation/object_gaussian_{noise_intensity.replace('.', '')}_fixMutRatio_centerXY_{mutate_ratio.replace('.', '')}")
        elif mutate_type == "background":
            output_path = os.path.join(output_path, f"BackgroundGaussianMutation/background_gaussian_{noise_intensity.replace('.', '_')}")
        return output_path

    def test_mutate_single_image_object(self):
        if os.path.isfile("/root/MetaHand/data_pilot_test/test_mutate"):
            shutil.rmtree("./MetaHand/data_pilot_test/test_mutate")
        self.mutate_image("file", "/root/MetaHand/data_pilot_test/images/000fbcd9-frame144.jpg",
                          "/root/MetaHand/data_pilot_test/labels/000fbcd9-frame144.txt",
                          "/root/MetaHand/data_pilot_test/test_mutate", "object", "0.9", "16.0", "darknet")
        assert os.path.isfile(
            "./MetaHand/data_pilot_test/test_mutate/ObjectGaussianMutation/object_gaussian_160_fixMutRatio_centerXY_09/000fbcd9-frame144.jpg"), "Mutated file is not generated"

    def test_mutate_single_image_background(self):
        if os.path.isfile("/root/MetaHand/data_pilot_test/test_mutate"):
            shutil.rmtree("./MetaHand/data_pilot_test/test_mutate")
        self.mutate_image("file", "/root/MetaHand/data_pilot_test/images/000fbcd9-frame144.jpg",
                          "/root/MetaHand/data_pilot_test/labels/000fbcd9-frame144.txt",
                          "/root/MetaHand/data_pilot_test/test_mutate", "background", "0.9", "16.0", "darknet")
        assert os.path.isfile(
            "./MetaHand/data_pilot_test/test_mutate/BackgroundGaussianMutation/background_gaussian_16_0/000fbcd9-frame144.jpg"), "Mutated file is not generated"

    def test_mutate_multi_images_object(self):
        if os.path.isfile("/root/MetaHand/data_pilot_test/test_mutate"):
            shutil.rmtree("./MetaHand/data_pilot_test/test_mutate")
        self.mutate_image("directory", "/root/MetaHand/tools/yolov7/demo/images/train",
                          "/root/MetaHand/tools/yolov7/demo/labels/train", "/root/MetaHand/tools/yolov7/demo/ObjectGaussianMutation",
                          "object", "0.3", "16.0", "darknet")
        # assert os.path.isfile(
        #     "./MetaHand/data_pilot_test/test_mutate/ObjectGaussianMutation/object_gaussian_160_fixMutRatio_centerXY_09/000fbcd9-frame144.jpg"), "Mutated file is not generated"
        # assert os.path.isfile(
        #     "./MetaHand/data_pilot_test/test_mutate/ObjectGaussianMutation/object_gaussian_160_fixMutRatio_centerXY_09/0013ad86-frame8912.jpg"), "Mutated file is not generated"
        # assert os.path.isfile(
        #     "./MetaHand/data_pilot_test/test_mutate/ObjectGaussianMutation/object_gaussian_160_fixMutRatio_centerXY_09/0016c94e-ae84057b-8.jpg"), "Mutated file is not generated"
        # assert os.path.isfile(
        #     "./MetaHand/data_pilot_test/test_mutate/ObjectGaussianMutation/object_gaussian_160_fixMutRatio_centerXY_09/0018df51-IMG_20201019_155102.jpg"), "Mutated file is not generated"

    def test_mutate_multi_images_background(self):
        print("This test case will take longer time for processing, please wait for 1-2 minutes")
        if os.path.isfile("/root/MetaHand/data_pilot_test/test_mutate"):
            shutil.rmtree("./MetaHand/data_pilot_test/test_mutate")
        self.mutate_image("directory", "/root/MetaHand/data_pilot_test/images/",
                          "/root/MetaHand/data_pilot_test/labels/", "/root/MetaHand/data_pilot_test/test_mutate",
                          "background", "0.9", "16.0", "darknet")
        assert os.path.isfile(
            "./MetaHand/data_pilot_test/test_mutate/BackgroundGaussianMutation/background_gaussian_16_0/000fbcd9-frame144.jpg"), "Mutated file is not generated"
        assert os.path.isfile(
            "./MetaHand/data_pilot_test/test_mutate/BackgroundGaussianMutation/background_gaussian_16_0/0013ad86-frame8912.jpg"), "Mutated file is not generated"
        assert os.path.isfile(
            "./MetaHand/data_pilot_test/test_mutate/BackgroundGaussianMutation/background_gaussian_16_0/0016c94e-ae84057b-8.jpg"), "Mutated file is not generated"
        assert os.path.isfile(
            "./MetaHand/data_pilot_test/test_mutate/BackgroundGaussianMutation/background_gaussian_16_0/0018df51-IMG_20201019_155102.jpg"), "Mutated file is not generated"

if __name__ == "__main__":
    container_name = "DNNTesting"
    dnnTest = DNNTest(container_name)
    # dnnTest.numerical_analysis("TensorFuzz.pbtxt")
    # path = dnnTest.detect_yolov7("/root/MetaHand/tools/yolov7/pilotstudy/images/val/ff1af9a2-frame2811.jpg", "/root/MetaHand/tools/yolov7/runs/train/pilotstudy/weights/best.pt")
    # dnnTest.train_yolov7(proj_name="pilotstudy", data_path="/root/MetaHand/tools/yolov7/pilotstudy/data.yaml")
    # dnnTest.evaluate_yolov7(
    #     data_dir="/root/MetaHand/tools/yolov7/company",
    #     weights_path="/root/MetaHand/tools/yolov7/runs/train/company_640/weights/best.pt",
    # )
    # dnnTest.repair_yolov7(
    #     data_dir="/root/MetaHand/tools/yolov7/company",
    #     weights_path="/root/MetaHand/tools/yolov7/runs/train/company_640/weights/best.pt",
    # )
    # dnnTest.train_yolov7(
    #     proj_name="demo",
    #     data_path="/root/MetaHand/tools/yolov7/demo/data.yaml",
    #     cfg_path="cfg/training/yolov7-tiny.yaml"
    # )

    # dnnTest.detect_yolov7_dir(weights_path="/root/MetaHand/tools/yolov7/runs/train/yolov7_object_gaussian_160_fixMutRatio_centerXY_03_640/weights/best.pt")
    # for mutate_ratio in ["01", "02", "03", "04", "05", "06", "07", "08", "09"]:
    #     dnnTest.repair_yolov7(weights_path="/root/MetaHand/tools/yolov7/runs/train/pilotstudy_320/weights/best.pt",
    #                           img_size=320, mutate_ratio=mutate_ratio, mutate_strength=320)
    # dnnTest.test_mutate_single_image_object()
    # dnnTest.test_mutate_single_image_background()
    dnnTest.test_mutate_multi_images_object()
    # dnnTest.test_mutate_multi_images_background()

