<template>
  <div id="app-container">
    <el-container>
      <el-header height="56px">
        <div class="header-content">
          <h1 class="title">点云3D渲染 - Web管理端</h1>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ElContainer, ElHeader, ElMain } from 'element-plus'
</script>

<style scoped>
#app-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}
.el-header {
  background: #1a1a2e;
  border-bottom: 2px solid #16213e;
  display: flex;
  align-items: center;
}
.header-content {
  display: flex;
  align-items: center;
  width: 100%;
}
.title {
  color: #e0e0e0;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}
.el-main {
  padding: 0;
  height: calc(100vh - 56px);
  overflow: hidden;
}
</style>
