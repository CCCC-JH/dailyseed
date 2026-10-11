package com.dailyseed.user;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/**
 * 把请求头里的设备 ID 换成 userId。
 *
 * <p>身份只认设备（{@code X-Device-Id}），**不信任前端传来的 userId**——
 * 否则任何人改个数字就能看别人的花园。
 */
@Component
public class DeviceUserResolver {

    private final UserStore users;

    public DeviceUserResolver(UserStore users) {
        this.users = users;
    }

    public long require(String deviceId) {
        return users.findUserIdByDevice(deviceId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED, "先调 POST /api/session 建匿名身份"));
    }
}
