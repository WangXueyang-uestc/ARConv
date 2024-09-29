import torch
import torch.nn as nn
import scipy.io as sio
import os
import torch.nn.functional as F


class mySin(torch.nn.Module):  # sin激活函数
    def __init__(self):
        super().__init__()

    def forward(self, x):
        x = torch.sin(x)
        return x


class RectConv2d(nn.Module):
    def __init__(self, inc, outc, kernel_size=3, padding=1, stride=1, l_max=9, w_max=9, flag=False):
        super(RectConv2d, self).__init__()
        self.lmax = l_max
        self.wmax = w_max
        self.nmax = l_max * w_max
        self.inc = inc
        self.outc = outc
        self.kernel_size = kernel_size
        self.padding = padding
        self.stride = stride
        self.zero_padding = nn.ZeroPad2d(padding)
        self.flag = flag
        self.i_list = [9, 15, 21, 25, 35, 49]

        self.convs = nn.ModuleList(
            [
                nn.Conv3d(
                    inc, outc, kernel_size=(i, 1, 1), stride=(i, 1, 1), bias=False
                )
                for i in self.i_list
            ]
        )
        self.m_conv = nn.Sequential(
            nn.Conv2d(inc, outc, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(outc, outc, kernel_size=3, padding=1, stride=stride)
        )

        self.b_conv = nn.Sequential(
            nn.Conv2d(inc, outc, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(outc, outc, kernel_size=3, padding=1, stride=stride)
        )

        self.l_conv = nn.Sequential(
            nn.Conv2d(inc, inc, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(inc, inc // 2, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(inc // 2, 1, kernel_size=3, padding=1, stride=stride)
        )
        self.l_sig = nn.Sigmoid()
        self.w_conv = nn.Sequential(
            nn.Conv2d(inc, inc, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(inc, inc // 2, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(inc // 2, 1, kernel_size=3, padding=1, stride=stride)
        )
        self.w_sig = nn.Sigmoid()
        self.theta_conv = nn.Sequential(
            nn.Conv2d(inc, inc, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(inc, inc // 2, kernel_size=3, padding=1, stride=stride),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv2d(inc // 2, 1, kernel_size=3, padding=1, stride=stride),
            nn.Tanh()
        )

        self.m_conv[0].register_full_backward_hook(self._set_lr)
        self.b_conv[0].register_full_backward_hook(self._set_lr)
        self.l_conv[0].register_full_backward_hook(self._set_lr)
        self.l_conv[2].register_full_backward_hook(self._set_lr)
        self.w_conv[0].register_full_backward_hook(self._set_lr)
        self.w_conv[2].register_full_backward_hook(self._set_lr)
        self.theta_conv[0].register_full_backward_hook(self._set_lr)
        self.theta_conv[2].register_full_backward_hook(self._set_lr)

        nn.init.kaiming_normal_(self.b_conv[0].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.b_conv[3].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.m_conv[0].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.m_conv[3].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.l_conv[0].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.l_conv[3].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.l_conv[6].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.w_conv[0].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.w_conv[3].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.w_conv[6].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.theta_conv[0].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.theta_conv[3].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.theta_conv[6].weight, nonlinearity='relu')

        nn.init.kaiming_normal_(self.convs[0].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.convs[1].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.convs[2].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.convs[3].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.convs[4].weight, nonlinearity='relu')
        nn.init.kaiming_normal_(self.convs[5].weight, nonlinearity='relu')

    @staticmethod
    def _set_lr(module, grad_input, grad_output):
        grad_input = tuple(g * 0.1 if g is not None else None for g in grad_input)
        grad_output = tuple(g * 0.1 if g is not None else None for g in grad_output)
        return grad_input

    def forward(self, x, epoch, label, nx, ny):
        bias = self.b_conv(x)
        m = self.m_conv(x)
        l = self.l_sig(self.l_conv(x) - 2) * (self.lmax - 1) + 1  # b, 1, h, w
        w = self.w_sig(self.w_conv(x) - 2) * (self.wmax - 1) + 1  # b, 1, h, w
        theta = self.theta_conv(x) * 3.1415926  # b, 1, h, w
        flattern_l = l.view(-1)
        flattern_w = w.view(-1)
        flattern_theta = theta.view(-1)
        mean_l = flattern_l.mean()
        mean_w = flattern_w.mean()
        mean_theta = flattern_theta.mean()
        # var_l = flattern_l.var()
        # var_w = flattern_w.var()
        # var_theta = flattern_theta.var()
        print(mean_l, mean_w, mean_theta)
        # print(var_l, var_w, var_theta)
        if epoch < 100:
            mean_l = l.mean(dim=0).mean(dim=1).mean(dim=1)
            mean_w = w.mean(dim=0).mean(dim=1).mean(dim=1)
            N_X = int(mean_l // 1)
            N_Y = int(mean_w // 1)
            if N_X % 2 == 0:
                N_X -= 1
            if N_Y % 2 == 0:
                N_Y -= 1
            if N_X < 3:
                N_X = 3
            if N_Y < 3:
                N_Y = 3
        elif epoch == 100:
            mean_l = l.mean(dim=0).mean(dim=1).mean(dim=1)
            mean_w = w.mean(dim=0).mean(dim=1).mean(dim=1)
            N_X = int(mean_l // 1)
            N_Y = int(mean_w // 1)
            if N_X % 2 == 0:
                N_X -= 1
            if N_Y % 2 == 0:
                N_Y -= 1
            if N_X < 3:
                N_X = 3
            if N_Y < 3:
                N_Y = 3
            tensor_x = torch.tensor([N_X, N_Y], dtype=torch.float32).cuda()
            tensor_x = tensor_x.cpu().numpy()
            save_path = "models_mats/x_" + str(label) + ".mat"
            save_dir = os.path.dirname(save_path)
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            sio.savemat(save_path, {"x": tensor_x})
        else:
            N_X = nx
            N_Y = ny
        N = N_X * N_Y
        print(N_X, N_Y)
        l = l.repeat([1, N, 1, 1])
        w = w.repeat([1, N, 1, 1])
        offset = torch.cat((l, w), dim=1)
        dtype = offset.data.type()
        if self.padding:
            x = self.zero_padding(x)
        p = self._get_p(offset, dtype, N_X, N_Y, theta)  # (b, 2*N, h, w)
        p = p.contiguous().permute(0, 2, 3, 1)  # (b, h, w, 2*N)
        q_lt = p.detach().floor()
        q_rb = q_lt + 1
        q_lt = torch.cat(
            [
                torch.clamp(q_lt[..., :N], 0, x.size(2) - 1),
                torch.clamp(q_lt[..., N:], 0, x.size(3) - 1),
            ],
            dim=-1,
        ).long()
        q_rb = torch.cat(
            [
                torch.clamp(q_rb[..., :N], 0, x.size(2) - 1),
                torch.clamp(q_rb[..., N:], 0, x.size(3) - 1),
            ],
            dim=-1,
        ).long()
        q_lb = torch.cat([q_lt[..., :N], q_rb[..., N:]], dim=-1)
        q_rt = torch.cat([q_rb[..., :N], q_lt[..., N:]], dim=-1)
        # clip p
        p = torch.cat(
            [
                torch.clamp(p[..., :N], 0, x.size(2) - 1),
                torch.clamp(p[..., N:], 0, x.size(3) - 1),
            ],
            dim=-1,
        )

        # bilinear kernel (b, h, w, N)
        g_lt = (1 + (q_lt[..., :N].type_as(p) - p[..., :N])) * (
                1 + (q_lt[..., N:].type_as(p) - p[..., N:])
        )
        g_rb = (1 - (q_rb[..., :N].type_as(p) - p[..., :N])) * (
                1 - (q_rb[..., N:].type_as(p) - p[..., N:])
        )
        g_lb = (1 + (q_lb[..., :N].type_as(p) - p[..., :N])) * (
                1 - (q_lb[..., N:].type_as(p) - p[..., N:])
        )
        g_rt = (1 - (q_rt[..., :N].type_as(p) - p[..., :N])) * (
                1 + (q_rt[..., N:].type_as(p) - p[..., N:])
        )
        # (b, c, h, w, N)
        x_q_lt = self._get_x_q(x, q_lt, N)
        x_q_rb = self._get_x_q(x, q_rb, N)
        x_q_lb = self._get_x_q(x, q_lb, N)
        x_q_rt = self._get_x_q(x, q_rt, N)
        # (b, c, h, w, N)
        x_offset = (
                g_lt.unsqueeze(dim=1) * x_q_lt
                + g_rb.unsqueeze(dim=1) * x_q_rb
                + g_lb.unsqueeze(dim=1) * x_q_lb
                + g_rt.unsqueeze(dim=1) * x_q_rt
        )
        x_offset = self._reshape_x_offset(x_offset)
        index = self.i_list.index(N)
        conv = self.convs[index]
        x_offset = conv(x_offset)
        x_offset = torch.squeeze(x_offset, dim=2)
        out = x_offset * m + bias
        return out

    def _get_p_n(self, N, dtype, n_x, n_y):
        p_n_x, p_n_y = torch.meshgrid(
            torch.arange(-(n_x - 1) // 2, (n_x - 1) // 2 + 1),
            torch.arange(-(n_y - 1) // 2, (n_y - 1) // 2 + 1),
        )
        p_n = torch.cat([torch.flatten(p_n_x), torch.flatten(p_n_y)], 0)
        p_n = p_n.view(1, 2 * N, 1, 1).type(dtype)
        return p_n

    def _get_p_0(self, h, w, N, dtype):
        p_0_x, p_0_y = torch.meshgrid(
            torch.arange(1, h * self.stride + 1, self.stride),
            torch.arange(1, w * self.stride + 1, self.stride),
        )
        p_0_x = torch.flatten(p_0_x).view(1, 1, h, w).repeat(1, N, 1, 1)
        p_0_y = torch.flatten(p_0_y).view(1, 1, h, w).repeat(1, N, 1, 1)
        p_0 = torch.cat([p_0_x, p_0_y], 1).type(dtype)
        return p_0

    def _get_p(self, offset, dtype, n_x, n_y, theta):
        N, h, w = offset.size(1) // 2, offset.size(2), offset.size(3)
        L, W = offset.split([N, N], dim=1)
        L = L / n_x
        W = W / n_y
        offsett = torch.cat([L, W], dim=1)
        p_n = self._get_p_n(N, dtype, n_x, n_y)
        p_n = p_n.repeat([1, 1, h, w])
        p_x, p_y = p_n.split([N, N], dim=1)
        p_xx = p_x * torch.cos(theta) - p_y * torch.sin(theta)
        p_yy = p_x * torch.sin(theta) + p_y * torch.cos(theta)
        p_n = torch.cat([p_xx, p_yy], dim=1)  # b, 2N, h, w
        p_0 = self._get_p_0(h, w, N, dtype)
        p = p_0 + offsett * p_n
        return p

    def _get_x_q(self, x, q, N):
        b, h, w, _ = q.size()
        padded_w = x.size(3)
        c = x.size(1)
        x = x.contiguous().view(b, c, -1)
        index = q[..., :N] * padded_w + q[..., N:]
        index = (
            index.contiguous()
            .unsqueeze(dim=1)
            .expand(-1, c, -1, -1, -1)
            .contiguous()
            .view(b, c, -1)
        )
        x_offset = x.gather(dim=-1, index=index).contiguous().view(b, c, h, w, N)
        return x_offset

    @staticmethod
    def _reshape_x_offset(x_offset):
        b, c, h, w, N = x_offset.size()
        x_offset = x_offset.permute(0, 1, 4, 2, 3)
        return x_offset


class RectB(nn.Module):
    def __init__(self, in_planes, flag=False):
        super(RectB, self).__init__()
        self.flag = flag
        self.conv1 = RectConv2d(in_planes, in_planes, 3, 1, 1)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = RectConv2d(in_planes, in_planes, 3, 1, 1, flag=self.flag)

    def forward(self, x, epoch, label1, label2, nx1, ny1, nx2, ny2):
        res = self.conv1(x, epoch, label1, nx1, ny1)
        res = self.relu(res)
        res = self.conv2(res, epoch, label2, nx2, ny2)
        x = x + res
        return x

class ConvDown(nn.Module):
    def __init__(self, in_channels, dsconv=True, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if dsconv:
            self.conv = nn.Sequential(
                nn.Conv2d(in_channels, in_channels, 2, 2, 0),
                nn.LeakyReLU(inplace=True),
                nn.Conv2d(in_channels, in_channels, 3, 1, 1, groups=in_channels, bias=False),
                nn.Conv2d(in_channels, in_channels * 2, 1, 1, 0)
            )
        else:
            self.conv = nn.Sequential(
                nn.Conv2d(in_channels, in_channels, 3, 2, 1),
                nn.LeakyReLU(inplace=True),
                nn.Conv2d(in_channels, in_channels * 2, 3, 1, 1)
            )

    def forward(self, x):
        return self.conv(x)


class ConvUp(nn.Module):
    def __init__(self, in_channels, dsconv=True, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.conv1 = nn.ConvTranspose2d(in_channels, in_channels // 2, 2, 2, 0)
        if dsconv:
            self.conv2 = nn.Sequential(
                nn.Conv2d(in_channels // 2, in_channels // 2, 3, 1, 1, groups=in_channels // 2, bias=False),
                nn.Conv2d(in_channels // 2, in_channels // 2, 1, 1, 0)
            )
        else:
            self.conv2 = nn.Conv2d(in_channels // 2, in_channels // 2, 3, 1, 1)

    def forward(self, x, y):
        x = F.leaky_relu(self.conv1(x))
        x = x + y
        x = F.leaky_relu(self.conv2(x))
        return x


class RECTNET(nn.Module):
    def __init__(self):
        super(RECTNET, self).__init__()
        self.head_conv = nn.Conv2d(9, 32, 3, 1, 1)
        self.rb1 = RectB(32, flag=True)
        self.down1 = ConvDown(32)
        self.rb2 = RectB(64)
        self.down2 = ConvDown(64)
        self.rb3 = RectB(128)
        self.up1 = ConvUp(128)
        self.rb4 = RectB(64)
        self.up2 = ConvUp(64)
        self.rb5 = RectB(32)
        self.tail_conv = nn.Conv2d(32, 8, 3, 1, 1)

    def forward(self, pan, lms, epoch, nx1=3, ny1=3, nx2=3, ny2=3, nx3=3, ny3=3, nx4=3, ny4=3, nx5=3, ny5=3,
                nx6=3, ny6=3, nx7=3, ny7=3, nx8=3, ny8=3, nx9=3, ny9=3, nx10=3, ny10=3):
        x1 = torch.cat([pan, lms], dim=1)
        x1 = self.head_conv(x1)
        x1 = self.rb1(x1, epoch, 1, 2, nx1, ny1, nx2, ny2)
        x2 = self.down1(x1)
        x2 = self.rb2(x2, epoch, 3, 4, nx3, ny3, nx4, ny4)
        x3 = self.down2(x2)
        x3 = self.rb3(x3, epoch, 5, 6, nx5, ny5, nx6, ny6)
        x4 = self.up1(x3, x2)
        del x2
        x4 = self.rb4(x4, epoch, 7, 8, nx7, ny7, nx8, ny8)
        x5 = self.up2(x4, x1)
        del x1
        x5 = self.rb5(x5, epoch, 9, 10, nx9, ny9, nx10, ny10)
        x5 = self.tail_conv(x5)
        return lms + x5