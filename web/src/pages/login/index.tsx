import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input, Checkbox, Form, addToast } from "@heroui/react";
import { Icon } from "@iconify/react";

import { authApi } from "@/services/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [isVisible, setIsVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  const toggleVisibility = () => setIsVisible(!isVisible);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    
    const formData = new FormData(event.currentTarget);
    const account = formData.get("account") as string;
    const password = formData.get("password") as string;
    const remember = formData.get("remember") === "on";

    if (!account || !password) {
      addToast({
        title: "错误",
        description: "请输入账号和密码",
        color: "danger",
      });
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.login({ account, password });


      if (response.success && response.data) {
        // 保存用户信息
        const userData = response.data;
        if (remember) {
          localStorage.setItem("user", JSON.stringify(userData));
        } else {
          sessionStorage.setItem("user", JSON.stringify(userData));
        }

        addToast({
          title: "登录成功",
          description: `欢迎回来，${userData.account}`,
          color: "success",
        });

        // 跳转到首页
        navigate("/traders");
      } else {
        // 登录失败（API 返回 success: false）
        addToast({
          title: "登录失败",
          description: response.error || "账号或密码错误",
          color: "danger",
        });
      }
    } catch (error: any) {
      addToast({
        title: "登录失败",
        description: error.response?.data?.error || "账号或密码错误",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-default-100 to-default-50">
      <div className="rounded-large bg-content1 shadow-large flex w-full max-w-sm flex-col gap-4 px-8 pt-6 pb-10">
        <div className="flex flex-col items-center gap-2 pb-4">
          <Icon icon="lucide:bot" className="text-primary" width={48} />
          <p className="text-2xl font-semibold">
            Auto Trading
          </p>
          <p className="text-default-500 text-sm">
            登录您的账户
          </p>
        </div>
        
        <Form 
          className="flex flex-col gap-4" 
          validationBehavior="native" 
          onSubmit={handleSubmit}
        >
          <Input
            isRequired
            label="账号"
            labelPlacement="outside"
            name="account"
            placeholder="请输入账号"
            type="text"
            variant="bordered"
            startContent={
              <Icon 
                className="text-default-400 pointer-events-none" 
                icon="lucide:user" 
                width={18}
              />
            }
          />
          <Input
            isRequired
            endContent={
              <button type="button" onClick={toggleVisibility}>
                {isVisible ? (
                  <Icon
                    className="text-default-400 pointer-events-none text-xl"
                    icon="solar:eye-closed-linear"
                  />
                ) : (
                  <Icon
                    className="text-default-400 pointer-events-none text-xl"
                    icon="solar:eye-bold"
                  />
                )}
              </button>
            }
            label="密码"
            labelPlacement="outside"
            name="password"
            placeholder="请输入密码"
            type={isVisible ? "text" : "password"}
            variant="bordered"
            startContent={
              <Icon 
                className="text-default-400 pointer-events-none" 
                icon="lucide:lock" 
                width={18}
              />
            }
          />
          <div className="flex w-full items-center px-1 py-2">
            <Checkbox defaultSelected name="remember" size="sm">
              记住我
            </Checkbox>
          </div>
          <Button 
            className="w-full" 
            color="primary" 
            type="submit"
            isLoading={loading}
            size="lg"
          >
            登 录
          </Button>
        </Form>
      </div>
    </div>
  );
}
