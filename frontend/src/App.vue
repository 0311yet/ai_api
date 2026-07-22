<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, darkTheme } from 'naive-ui'

const themeOverrides = {
  common: {
    primaryColor: '#409eff',
    primaryColorHover: '#66b1ff',
    primaryColorPressed: '#3a8ee6',
    errorColor: '#D03050',
    successColor: '#18A058',
    warningColor: '#F0A020',
    infoColor: '#2080F0',
    bodyColor: '#12121d',
    cardColor: '#1f1e2a',
    modalColor: '#1f1e2a',
    popoverColor: '#1f1e2a',
    tableColor: '#1f1e2a',
    inputColor: '#1f1e2a',
    borderColor: '#2e2e42',
    textColorBase: '#ffffff',
    textColor1: '#ffffff',
    textColor2: '#e3e0f1',
    textColor3: '#c0c7d4',
    textColorDisabled: '#8c8c8c',
    fontFamily: 'Inter, system-ui, sans-serif',
    fontFamilyMono: 'JetBrains Mono, monospace',
  },
  DataTable: {
    thColor: '#292935',
    tdColor: '#1f1e2a',
    borderColor: '#2e2e42',
    thTextColor: '#c0c7d4',
    tdTextColor: '#e3e0f1',
  },
  Button: {
    colorPrimary: '#409eff',
    colorHoverPrimary: '#66b1ff',
    colorPressedPrimary: '#3a8ee6',
    textColorPrimary: '#ffffff',
  },
  Input: {
    color: '#1f1e2a',
    colorFocus: '#1f1e2a',
    borderColor: '#2e2e42',
    borderColorFocus: '#409eff',
    textColor: '#ffffff',
    placeholderColor: '#8c8c8c',
  },
  Modal: {
    color: '#1f1e2a',
    textColor: '#ffffff',
  },
  Card: {
    color: '#1f1e2a',
    borderColor: '#2e2e42',
    textColor: '#ffffff',
  },
  Tag: {
    borderRadius: '9999px',
  },
  Pagination: {
    buttonColor: '#1f1e2a',
    buttonColorHover: '#292935',
  },
}
</script>

<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <router-view />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>