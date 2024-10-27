import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import * as Comfyui from "../lib/comfyui-stack";
import { defaultParameter } from "../parameter";

test("Snapshot test", () => {
  const app = new cdk.App();
  const stack = new Comfyui.ComfyUIStack(app, "TestStack", {
    env: {
      account: "000000000000",
      region: "us-west-2",
    },
    ...defaultParameter,
  });
  const template = Template.fromStack(stack);
  expect(template).toMatchSnapshot();
});
