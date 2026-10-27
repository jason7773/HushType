plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// 版本號：發佈新版時改這裡（versionCode 每次都要加 1）
val appVersionName = "0.1.1"
val appVersionCode = 2

// CI 會用 GitHub Secrets 裡的簽章金鑰；本機建置時用 Android 的除錯金鑰
val keystorePath: String? = System.getenv("HUSHTYPE_KEYSTORE")

android {
    namespace = "io.github.jason7773.hushtype"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.jason7773.hushtype"
        minSdk = 30
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName
    }

    signingConfigs {
        if (keystorePath != null) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("HUSHTYPE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("HUSHTYPE_KEY_ALIAS")
                keyPassword = System.getenv("HUSHTYPE_KEY_PASSWORD") ?: System.getenv("HUSHTYPE_KEYSTORE_PASSWORD")
                storeType = System.getenv("HUSHTYPE_KEYSTORE_TYPE") ?: "pkcs12"
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = if (keystorePath != null) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        buildConfig = true
    }

    // 不把相依套件清單（Google 加密的中繼資料）放進 APK
    dependenciesInfo {
        includeInApk = false
        includeInBundle = false
    }

    packaging {
        resources {
            excludes += listOf("/META-INF/*.kotlin_module", "/META-INF/*.version", "/kotlin/**", "DebugProbesKt.bin")
        }
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
